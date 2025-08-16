"""
Create .conda packages from wheels.

Create wheels from pypa projects.

Originally from conda-pupa by Daniel Holth <dholth@gmail.com>
https://github.com/dholth/conda-pupa
Now integrated into conda-pypi
"""

from __future__ import annotations

import base64
import csv
import hashlib
import itertools
import json
import logging
import os
import subprocess
import sys
import tempfile
from importlib.metadata import PathDistribution
from pathlib import Path
from typing import Optional

from conda_package_streaming.create import conda_builder

from build import ProjectBuilder

from . import dependencies, installer, paths
from .conda_build_utils import PathType, sha256_checksum
from .translate import CondaMetadata

logger = logging.getLogger(__name__)


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
                "path_type": str(PathType.softlink if entry.is_symlink() else PathType.hardlink),
                "sha256": sha256_checksum(entry.path, entry),
                "size_in_bytes": st_size,
            }
        else:
            logger.debug(f"Not regular file: {entry}")
            # will Python's tarfile add pipes, device nodes to the archive?


def json_dumps(object):
    """
    Consistent json formatting.
    """
    return json.dumps(object, indent=2, sort_keys=True)


def flatten(iterable):
    return [*itertools.chain(*iterable)]


def build_pypa(
    path: Path,
    output_path,
    prefix: Path,
    distribution="editable",
):
    """
    Args:
        distribution: "editable" or "wheel"
    """
    python_executable = str(paths.get_python_executable(prefix))

    builder = ProjectBuilder(path, python_executable=python_executable)

    build_system_requires = builder.build_system_requires
    for _retry in range(2):
        try:
            missing = dependencies.check_dependencies(build_system_requires, prefix=prefix)
            break
        except dependencies.MissingDependencyError as e:
            dependencies.ensure_requirements(e.dependencies, prefix=prefix)

    logger.info(f"Installing requirements for build system: {missing}")
    # does flatten() work for a deeper dependency chain?
    dependencies.ensure_requirements(flatten(missing), prefix=prefix)

    requirements = builder.check_dependencies(distribution)
    logger.info(f"Additional requirements for {distribution}: {requirements}")
    dependencies.ensure_requirements(flatten(requirements), prefix=prefix)

    editable_file = builder.build(distribution, output_path)
    logger.info(f"The wheel is at {editable_file}")

    return editable_file


def build_conda(
    whl,
    build_path: Path,
    output_path: Path,
    python_executable,
    project_path: Optional[Path] = None,
    is_editable=False,
    skip_name_mapping: bool = False,
):
    if not build_path.exists():
        build_path.mkdir()

    installer.install_pip(python_executable, whl, build_path)

    site_packages = build_path / "site-packages"
    dist_info = next(site_packages.glob("*.dist-info"))
    metadata = CondaMetadata.from_distribution(
        PathDistribution(dist_info), skip_name_mapping=skip_name_mapping
    )
    record = metadata.package_record.to_index_json()
    # XXX set build string as hash of pypa metadata so that conda can re-install
    # when project gains new entry-points, dependencies?

    file_id = f"{record['name']}-{record['version']}-{record['build']}"

    (build_path / "info").mkdir()
    (build_path / "info" / "index.json").write_text(json_dumps(record))
    (build_path / "info" / "about.json").write_text(json_dumps(metadata.about))

    # used especially for console_scripts
    if link_json := metadata.link_json():
        (build_path / "info" / "link.json").write_text(json_dumps(link_json))

    # Allow pip to list us as editable or show the path to our project.
    # XXX leaks path
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


def _is_vcs_url(url_str: str) -> bool:
    """
    Check if a string is a VCS URL.

    Args:
        url_str: String to check for VCS URL format

    Returns:
        True if the string is a VCS URL (git+, hg+, svn+, bzr+), False otherwise

    Examples:
        >>> _is_vcs_url("git+https://github.com/user/repo.git")
        True
        >>> _is_vcs_url("/path/to/local/dir")
        False
    """
    vcs_schemes = ("git+", "hg+", "svn+", "bzr+")
    return url_str.startswith(vcs_schemes)


def _parse_vcs_url(vcs_url: str) -> tuple[str, str, str | None]:
    """
    Parse a VCS URL to extract the VCS type, repository URL, and revision.

    Args:
        vcs_url: VCS URL like 'git+https://github.com/user/repo.git@tag#egg=name'

    Returns:
        Tuple of (vcs_type, repo_url, revision). revision is None if not specified.

    Raises:
        ValueError: If the VCS URL format is not supported

    Examples:
        >>> _parse_vcs_url("git+https://github.com/user/repo.git@v1.0#egg=pkg")
        ('git', 'https://github.com/user/repo.git', 'v1.0')
        >>> _parse_vcs_url("git+https://github.com/user/repo.git")
        ('git', 'https://github.com/user/repo.git', None)
    """
    # Remove the egg fragment if present
    if "#egg=" in vcs_url:
        vcs_url = vcs_url.split("#egg=")[0]

    # Map VCS prefixes to types and their lengths
    vcs_mapping = {
        "git+": ("git", 4),
        "hg+": ("hg", 3),
        "svn+": ("svn", 4),
        "bzr+": ("bzr", 4),
    }

    # Find matching VCS type
    vcs_type = None
    repo_part = None
    for prefix, (vcs_name, prefix_len) in vcs_mapping.items():
        if vcs_url.startswith(prefix):
            vcs_type = vcs_name
            repo_part = vcs_url[prefix_len:]
            break

    if vcs_type is None:
        raise ValueError(f"Unsupported VCS URL format: {vcs_url}")

    # Extract revision if present (after @)
    if "@" in repo_part:
        repo_url, revision = repo_part.rsplit("@", 1)
    else:
        repo_url = repo_part
        revision = None

    return vcs_type, repo_url, revision


def _clone_vcs_url(vcs_url: str, target_dir: Path) -> Path:
    """
    Clone a VCS URL to a target directory.

    Args:
        vcs_url: VCS URL like 'git+https://github.com/user/repo.git@tag#egg=name'
        target_dir: Directory to clone into

    Returns:
        Path to the cloned repository

    Raises:
        RuntimeError: If cloning fails
        NotImplementedError: If VCS type is not supported

    Examples:
        >>> target = Path("/tmp/clone")
        >>> result = _clone_vcs_url("git+https://github.com/user/repo.git@v1.0", target)
        >>> result.exists()
        True
    """
    vcs_type, repo_url, revision = _parse_vcs_url(vcs_url)

    # Create a subdirectory for the clone
    clone_dir = target_dir / "src"
    clone_dir.mkdir(parents=True, exist_ok=True)

    if vcs_type == "git":
        return _clone_git_repository(repo_url, revision, clone_dir)
    else:
        raise NotImplementedError(
            f"VCS type '{vcs_type}' is not yet supported. Only 'git' is currently implemented."
        )


def _clone_git_repository(repo_url: str, revision: str | None, clone_dir: Path) -> Path:
    """
    Clone a git repository with optional revision checkout.

    Args:
        repo_url: Git repository URL
        revision: Optional revision (branch, tag, or commit) to checkout
        clone_dir: Directory to clone into

    Returns:
        Path to the cloned repository

    Raises:
        RuntimeError: If git operations fail
    """
    if revision:
        # Try shallow clone with specific branch/tag first (more efficient)
        cmd = ["git", "clone", "--branch", revision, "--depth", "1", repo_url, str(clone_dir)]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            logger.info(f"Successfully shallow cloned {repo_url}@{revision} to {clone_dir}")
            return clone_dir

        # Fallback: full clone and checkout (for commits or complex refs)
        logger.debug(f"Shallow clone failed, falling back to full clone: {result.stderr}")
        cmd = ["git", "clone", repo_url, str(clone_dir)]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"Git clone failed: {result.stderr}")

        # Force checkout the specific revision
        cmd = ["git", "checkout", "--force", revision]
        result = subprocess.run(cmd, cwd=clone_dir, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"Git checkout of '{revision}' failed: {result.stderr}")

        logger.info(f"Successfully cloned {repo_url} and checked out {revision} to {clone_dir}")
    else:
        # Clone without specific revision (default branch)
        cmd = ["git", "clone", repo_url, str(clone_dir)]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"Git clone failed: {result.stderr}")

        logger.info(f"Successfully cloned {repo_url} to {clone_dir}")

    return clone_dir


def pypa_to_conda(
    project,
    prefix: Path,
    distribution="editable",
    output_path: Optional[Path] = None,
):
    """
    Convert a PyPA project to a conda package.

    Args:
        project: Project path (local directory) or VCS URL (git+https://...)
        prefix: Conda environment prefix path
        distribution: Distribution type ("editable" or "wheel")
        output_path: Optional output directory for the conda package

    Returns:
        Path to the created conda package

    Raises:
        RuntimeError: If VCS cloning or building fails
        NotImplementedError: If unsupported VCS type is used
    """
    project_str = str(project)

    # Determine if this is a VCS URL or local path
    if _is_vcs_url(project_str):
        return _build_from_vcs_url(project_str, prefix, distribution, output_path)
    else:
        return _build_from_local_path(Path(project), prefix, distribution, output_path)


def _build_from_vcs_url(
    vcs_url: str, prefix: Path, distribution: str, output_path: Optional[Path]
) -> Path:
    """Build conda package from VCS URL by cloning first."""
    with tempfile.TemporaryDirectory(prefix="vcs_clone") as vcs_temp_dir:
        vcs_temp_path = Path(vcs_temp_dir)
        actual_project_path = _clone_vcs_url(vcs_url, vcs_temp_path)

        return _build_conda_package(actual_project_path, prefix, distribution, output_path)


def _build_from_local_path(
    project_path: Path, prefix: Path, distribution: str, output_path: Optional[Path]
) -> Path:
    """Build conda package from local project path."""
    return _build_conda_package(project_path, prefix, distribution, output_path)


def _build_conda_package(
    project_path: Path, prefix: Path, distribution: str, output_path: Optional[Path]
) -> Path:
    """Common logic for building conda packages from a local project path."""
    # Set up output directory
    if not output_path:
        output_path = project_path / "build"
        if not output_path.exists():
            output_path.mkdir()

    with tempfile.TemporaryDirectory(prefix="conda") as tmp_path:
        tmp_path = Path(tmp_path)

        # Build the wheel/editable package
        wheel_path = build_pypa(project_path, tmp_path, prefix=prefix, distribution=distribution)

        # Convert wheel to conda package
        build_path = tmp_path / "build"
        package_conda = build_conda(
            wheel_path,
            build_path,
            output_path or tmp_path,
            sys.executable,
            project_path=project_path,
            is_editable=distribution == "editable",
        )

    return package_conda
