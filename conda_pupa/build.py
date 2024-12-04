"""
Create .conda packages from wheels.

Create wheels from pypa projects.
"""

import base64
import csv
import hashlib
import itertools
import json
import os
import sys
import tempfile
from importlib.metadata import PathDistribution
from pathlib import Path

from conda.cli.main import main_subshell
from conda_package_streaming.create import conda_builder

from build import ProjectBuilder, check_dependency

from . import installer
from .conda_build_utils import PathType, sha256_checksum
from .translate import CondaMetadata, requires_to_conda


def filter(tarinfo):
    """
    Anonymize uid/gid; exclude .git directories.
    """
    if tarinfo.name.endswith(".git"):
        return None
    tarinfo.uid = tarinfo.gid = 0
    tarinfo.uname = tarinfo.gname = ""
    return tarinfo


# see conda_build.build.build_info_files_json_v1
def paths_json(base: Path | str):
    """
    Build simple paths.json with only 'hardlink' or 'symlink' types.
    """
    base = str(base)

    if not base.endswith(os.sep):
        base = base + os.sep

    return {
        "paths": sorted(_paths(base, base), key=lambda entry: entry["_path"]),
        "paths_version": 1,
    }


def _paths(base, path, filter=lambda x: x.name != ".git"):
    for entry in os.scandir(path):
        # TODO convert \\ to /
        relative_path = entry.path[len(base) :]
        if relative_path == "info" or not filter(entry):
            continue
        if entry.is_dir():
            yield from _paths(base, entry.path, filter=filter)
        elif entry.is_file() or entry.is_symlink():
            try:
                st_size = entry.stat().st_size
            except FileNotFoundError:
                st_size = 0  # symlink to nowhere
            yield {
                "_path": relative_path,
                "path_type": str(
                    PathType.softlink if entry.is_symlink() else PathType.hardlink
                ),
                "sha256": sha256_checksum(entry.path, entry),
                "size_in_bytes": st_size,
            }
        else:
            print("Not regular file", entry)
            # will Python's tarfile add pipes, device nodes to the archive?



def json_dumps(object):
    """
    Consistent json formatting.
    """
    return json.dumps(object, indent=2, sort_keys=True)


def flatten(iterable):
    return [*itertools.chain(*iterable)]


def ensure_requirements(requirements):
    if requirements:
        conda_requirements, _ = requires_to_conda(requirements)
        # -y may be appropriate during tests only
        main_subshell("install", "-y", *conda_requirements)


def build_pypa(
    path: Path, output_path, python_executable: str, distribution="editable"
):
    """
    Args:
        distribution: "editable" or "wheel"
    """
    builder = ProjectBuilder(path, python_executable=python_executable)

    build_system_requires = builder.build_system_requires
    missing = {u for d in build_system_requires for u in check_dependency(d)}
    print("Installing requirements for build system:", missing)
    # does flatten() work for a deeper dependency chain?
    ensure_requirements(flatten(missing))

    requirements = builder.check_dependencies(distribution)
    print(f"Additional requirements for {distribution}:", requirements)
    ensure_requirements(flatten(requirements))

    editable_file = builder.build(distribution, output_path)
    print("The wheel is at", editable_file)

    return editable_file


def build_conda(
    whl,
    build_path: Path,
    output_path: Path,
    python_executable,
    project_path: Path | None = None,
    is_editable=False,
):
    if not build_path.exists():
        build_path.mkdir()

    installer.install_pip(python_executable, whl, build_path)

    site_packages = build_path / "site-packages"
    dist_info = next(site_packages.glob("*.dist-info"))
    metadata = CondaMetadata.from_distribution(PathDistribution(dist_info))
    record = metadata.package_record.to_index_json()
    # XXX set build string as hash of pypa metadata so that conda can re-install
    # when project gains new entry-points, dependencies?

    file_id = f"{record['name']}-{record['version']}-{record['build']}"

    (build_path / "info").mkdir()
    (build_path / "info" / "index.json").write_text(json_dumps(record))

    # used especially for console_scripts
    if link_json := metadata.link_json():
        (build_path / "info" / "link.json").write_text(json_dumps(link_json))

    # Allow pip to list us as editable
    if project_path:
        direct_url = project_path.absolute().as_uri()
        direct_url_path = dist_info / "direct_url.json"
        direct_url_path.write_text(
            json.dumps({"dir_info": {"editable": is_editable}, "url": direct_url})
        )
        record_path = dist_info / "RECORD"
        # Rewrite RECORD for any changed files
        update_RECORD(record_path, site_packages, direct_url_path)

    # Write conda's paths after all other changes
    paths = paths_json(build_path)

    (build_path / "info" / "paths.json").write_text(json_dumps(paths))

    with conda_builder(file_id, output_path) as tar:
        tar.add(build_path, "", filter=filter)

    return output_path / f"{file_id}.conda"


def update_RECORD(record_path: Path, base_path: Path, changed_path: Path):
    """
    Rewrite RECORD with new size, checksum for updated_file.
    """
    # note `installer` also has code to handle RECORD
    record_text = record_path.read_text()
    record_rows = list(csv.reader(record_text.splitlines()))

    relpath = str(changed_path.relative_to(base_path)).replace(os.sep, "/")
    for row in record_rows:
        if row[0] == relpath:
            data = changed_path.read_bytes()
            size = len(data)
            checksum = (
                base64.urlsafe_b64encode(hashlib.sha256(data).digest())
                .rstrip(b"=")
                .decode("utf-8")
            )
            row[1] = f"sha256={checksum}"
            row[2] = str(size)

    with record_path.open(mode="w", newline="", encoding="utf-8") as record_file:
        writer = csv.writer(record_file)
        writer.writerows(record_rows)


def pypa_to_conda(project, distribution="editable"):
    project = Path(project)
    with tempfile.TemporaryDirectory(prefix="conda", delete=False) as tmp_path:
        tmp_path = Path(tmp_path)
        output_path = Path(project / "build")
        if not output_path.exists():
            output_path.mkdir()
        normal_wheel = build_pypa(
            Path(project), tmp_path, sys.executable, distribution=distribution
        )
        build_path = tmp_path / "build"
        package_conda = build_conda(
            normal_wheel,
            build_path,
            tmp_path,
            sys.executable,
            project_path=project,
            is_editable=True,
        )
        print("Conda at", package_conda)
