"""
Build a Python project into an editable wheel, convert to a .conda and install
the .conda.
"""

import base64
import csv
import hashlib
import itertools
import json
import os
import subprocess
import sys
import tempfile
from importlib.metadata import PathDistribution
from pathlib import Path

from conda.cli.main import main_subshell
from packaging.utils import canonicalize_name

from build import ProjectBuilder, check_dependency

from . import build
from .create import conda_builder
from .translate import CondaMetadata, requires_to_conda


def normalize(name):
    return canonicalize_name(name)


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


def build_pypa(path: Path, output_path, python_executable, distribution="editable"):
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

    # could we find the local channel for conda-build, drop our new package
    # there and have it automatically be found
    command = [
        python_executable,
        "-m",
        "pip",
        "install",
        "--no-deps",
        "--target",
        str(build_path / "site-packages"),
        whl,
    ]
    subprocess.run(command, check=True)
    print("Installed to", build_path)

    site_packages = build_path / "site-packages"
    dist_info = next(site_packages.glob("*.dist-info"))
    metadata = CondaMetadata.from_distribution(PathDistribution(dist_info))
    record = metadata.package_record.to_index_json()
    # XXX set build string as hash of pypa metadata so that conda can re-install
    # when project gains new entry-points, dependencies?

    file_id = f"{record['name']}-{record['version']}-{record['build']}"

    (build_path / "info").mkdir()
    (build_path / "info" / "index.json").write_text(json_dumps(record))

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
    paths = build.paths_json(build_path)

    (build_path / "info" / "paths.json").write_text(json_dumps(paths))

    with conda_builder(file_id, output_path) as tar:
        tar.add(build_path, "", filter=build.filter)

    return output_path / f"{file_id}.conda"


def update_RECORD(record_path: Path, base_path: Path, changed_path: Path):
    """
    Rewrite RECORD with new size, checksum for updated_file.
    """
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


def editable(project, distribution="editable"):
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


if __name__ == "__main__":  # pragma: no cover
    editable(sys.argv[1])
