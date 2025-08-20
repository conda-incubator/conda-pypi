"""
Package building and metadata translation for conda-pypi.

This module handles:
1. Converting a Python wheels to a conda package
2. Building a conda package from Python project
3. Translating Python metadata to conda format
4. Managing package metadata and dependencies

Originally from conda-pupa by Daniel Holth <dholth@gmail.com>
https://github.com/dholth/conda-pupa
Now integrated and enhanced in conda-pypi
"""

from __future__ import annotations

import dataclasses
import itertools
import json
import logging
import os
import platform
import sys
import tempfile
import time
from importlib.metadata import Distribution, PathDistribution
from pathlib import Path
from typing import Any, TYPE_CHECKING, Optional, List, Dict

if TYPE_CHECKING:
    try:
        from importlib.metadata import PackageMetadata
    except ImportError:
        # Python < 3.10 doesn't have PackageMetadata as a separate class
        # In those versions, Distribution.metadata is an email.message.Message
        from email.message import Message as PackageMetadata

from build import ProjectBuilder
from conda.models.match_spec import MatchSpec
from conda_package_streaming.create import conda_builder
from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name
from installer import install
from installer.destinations import SchemeDictionaryDestination
from installer.sources import WheelFile

from .utils import PathType, sha256_checksum, get_python_executable
from .mapping import pypi_to_conda_name, conda_to_pypi_name

log = logging.getLogger(__name__)


def _get_script_kind():
    """Get the appropriate script kind for the current platform."""
    if os.name == "posix":
        return "posix"
    elif os.name == "nt":
        machine = platform.machine().lower()
        if machine in ("amd64", "x86_64"):
            return "win-amd64"
        elif machine == "arm64":
            return "win-arm64"
        elif machine in ("i386", "i686", "x86"):
            return "win-ia32"
        elif machine == "arm":
            return "win-arm"
        else:
            log.warning(f"Unknown Windows architecture '{machine}', defaulting to win-amd64")
            return "win-amd64"
    else:
        log.warning(f"Unknown platform '{os.name}', defaulting to posix")
        return "posix"


def get_python_version_from_executable(python_exe: Path) -> str:
    """Get Python version string from a Python executable."""
    import subprocess

    try:
        result = subprocess.run(
            [
                str(python_exe),
                "-c",
                "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        # Fallback to current Python version
        return f"{sys.version_info.major}.{sys.version_info.minor}"


def install_wheel(wheel_path: Path, install_dir: Path, python_exe: Path):
    """Install a wheel using the installer library."""
    # Get Python version for site-packages path from target environment
    python_version = get_python_version_from_executable(python_exe)
    site_packages = install_dir / "lib" / f"python{python_version}" / "site-packages"

    # Handler for installation directories and writing into them.
    destination = SchemeDictionaryDestination(
        {
            "platlib": str(site_packages),
            "purelib": str(site_packages),
            "headers": str(install_dir / "include"),
            "scripts": str(install_dir / "bin"),
            "data": str(install_dir),
        },
        interpreter=sys.executable,
        script_kind=_get_script_kind(),
    )

    # Install the wheel
    with WheelFile.open(wheel_path) as source:
        install(source, destination, {})

    log.info(f"Installed wheel {wheel_path} to {install_dir}")


class FileDistribution(Distribution):
    """
    Distribution from a file (e.g. a single `.metadata` fetched from PyPI)
    instead of a `*.dist-info` folder.
    """

    def __init__(self, raw_text):
        self.raw_text = raw_text

    def read_text(self, filename: str) -> Optional[str]:
        if filename == "METADATA":
            return self.raw_text
        else:
            return None

    def locate_file(self, path):
        """
        Given a path to a file in this distribution, return a path to it.
        """
        return None


@dataclasses.dataclass
class PackageRecord:
    """
    Represents conda package metadata that goes in info/index.json
    """

    name: str
    version: str
    subdir: str
    depends: List[str]
    extras: Dict[str, List[str]]
    build_number: int = 0
    build_text: str = "pypi"  # e.g. hash
    license_family: str = ""
    license: str = ""
    noarch: str = ""
    timestamp: int = 0

    def to_index_json(self):
        return {
            "build_number": self.build_number,
            "build": self.build,
            "depends": self.depends,
            "extras": self.extras,
            "license_family": self.license_family,
            "license": self.license,
            "name": self.name,
            "noarch": self.noarch,
            "subdir": self.subdir,
            "timestamp": self.timestamp,
            "version": self.version,
        }

    @property
    def build(self):
        return f"{self.build_text}_{self.build_number}"

    @property
    def stem(self):
        return f"{self.name}-{self.version}-{self.build}"


@dataclasses.dataclass
class CondaMetadata:
    """
    Complete conda package metadata including Python metadata, console scripts,
    package record, and about information.
    """

    metadata: PackageMetadata
    console_scripts: List[str]
    package_record: PackageRecord
    about: Dict[str, Any]

    def link_json(self) -> Optional[Dict]:
        """
        Generate info/link.json used for console scripts; None if empty.

        Note: The METADATA file (PackageRecord) does not list console scripts.
        """
        # XXX gui scripts?
        return {
            "noarch": {"entry_points": self.console_scripts, "type": "python"},
            "package_metadata_version": 1,
        }

    @classmethod
    def from_distribution(cls, distribution: Distribution, skip_name_mapping: bool = False):
        """
        Create CondaMetadata from a Distribution.

        Args:
            distribution: The Python distribution to convert
            skip_name_mapping: If True, skip grayskull mapping for the main package name.
                              This is useful for explicitly requested packages that should
                              be installed from PyPI rather than mapped to conda packages.
        """
        metadata = distribution.metadata

        python_version = metadata["requires-python"]
        requires_python = "python"
        if python_version:
            requires_python = f"python { python_version }"

        requirements, extras = requires_to_conda(distribution.requires)

        # conda does support ~=3.0.0 "compatibility release" matches
        depends = [requires_python] + requirements

        console_scripts = [
            f"{ep.name} = {ep.value}"
            for ep in distribution.entry_points
            if ep.group == "console_scripts"
        ]

        noarch = "python"

        # Common "about" keys
        # ['channels', 'conda_build_version', 'conda_version', 'description',
        # 'dev_url', 'doc_url', 'env_vars', 'extra', 'home', 'identifiers',
        # 'keywords', 'license', 'license_family', 'license_file', 'root_pkgs',
        # 'summary', 'tags']
        about = {
            "description": metadata.get("description", ""),
            "home": metadata.get("home-page", ""),
            "license": metadata.get("license", ""),
            "summary": metadata.get("summary", ""),
        }

        if skip_name_mapping:
            conda_name = metadata["name"]
        else:
            conda_name = pypi_to_conda_name(metadata["name"])

        package_record = PackageRecord(
            name=conda_name,
            version=metadata["version"],
            subdir="noarch",
            depends=depends,
            extras=extras,
            noarch=noarch,
            license=metadata.get("license", ""),
            timestamp=int(time.time()),
        )

        return cls(
            metadata=metadata,
            console_scripts=console_scripts,
            package_record=package_record,
            about=about,
        )


def requires_to_conda(requires: Optional[List[str]]):
    """
    Convert Python requirements to conda format.

    Args:
        requires: List of Python requirement strings

    Returns:
        Tuple of (requirements, extras) where requirements is a list of conda
        requirement strings and extras is a dict mapping extra names to their requirements.
    """
    from collections import defaultdict

    extras: Dict[str, List[str]] = defaultdict(list)
    requirements = []
    for requirement in [Requirement(dep) for dep in requires or []]:
        name = canonicalize_name(requirement.name)
        requirement.name = pypi_to_conda_name(name)
        as_conda = f"{requirement.name} {requirement.specifier}"

        if (marker := requirement.marker) is not None:
            for mark in marker._markers:
                if isinstance(mark, tuple):
                    var, _, value = mark
                    if str(var) == "extra":
                        extras[str(value)].append(as_conda)
        else:
            requirements.append(f"{requirement.name} {requirement.specifier}".strip())

    return requirements, dict(extras)


def conda_to_requires(matchspec: MatchSpec):
    """
    Convert conda MatchSpec to Python Requirement.

    Args:
        matchspec: Conda MatchSpec to convert

    Returns:
        Python Requirement object or None if conversion fails
    """
    name = matchspec.name
    pypi_name = conda_to_pypi_name(name)

    # Try different formats to find a valid requirement string
    for best_format in [
        f"{pypi_name} {matchspec.version}",
        f"{pypi_name}=={matchspec.version}",
        f"{pypi_name}",
    ]:
        try:
            return Requirement(best_format.replace(name, pypi_name))
        except InvalidRequirement:
            continue

    return None


def filter_tarinfo(tarinfo):
    """
    Filter function for tar archives: anonymize uid/gid and exclude .git directories.
    """
    if tarinfo.name.endswith(".git"):
        return None
    tarinfo.uid = tarinfo.gid = 0
    tarinfo.uname = tarinfo.gname = ""
    return tarinfo


def paths_json(base: Path | str):
    """
    Build simple paths.json with only 'hardlink' or 'symlink' types.

    This is used by conda to track files in packages.
    """
    base = str(base)

    if not base.endswith(os.sep):
        base = base + os.sep

    return {
        "paths": sorted(_paths(base, base), key=lambda entry: entry["_path"]),
        "paths_version": 1,
    }


def _paths(base, path, filter_func=lambda x: x.name != ".git"):
    """
    Recursively generate path entries for paths.json
    """
    base_path = Path(base)
    for entry in os.scandir(path):
        entry_path = Path(entry.path)
        relative_path = entry_path.relative_to(base_path).as_posix()
        if relative_path == "info" or not filter_func(entry):
            continue
        if entry.is_dir():
            yield from _paths(base, entry.path, filter_func)
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
            log.debug(f"Not regular file: {entry}")


def json_dumps(obj):
    """
    Consistent JSON formatting for conda packages.
    """
    return json.dumps(obj, indent=2, sort_keys=True)


def flatten(iterable):
    """
    Flatten nested iterables.
    """
    return [*itertools.chain(*iterable)]


def build_pypa(
    path: Path,
    output_path,
    prefix: Path,
    distribution="editable",
):
    """
    Build a conda package from a Python project (pyproject.toml, setup.py, etc.).

    Args:
        path: Path to the project directory
        output_path: Where to save the built package
        prefix: Conda environment prefix
        distribution: Type of distribution to build ("editable" or "wheel")
    """
    # Use the Python from the target environment
    python_exe = get_python_executable(prefix)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        if distribution == "editable":
            # Build editable wheel
            builder = ProjectBuilder(path)
            editable_file = builder.build("editable", str(tmpdir), {})

            # Convert editable wheel to conda package
            return build_conda(Path(editable_file), tmpdir, output_path, python_exe)
        else:
            # Build regular wheel
            builder = ProjectBuilder(path)
            wheel_file = builder.build("wheel", str(tmpdir), {})

            # Convert wheel to conda package
            return build_conda(Path(wheel_file), tmpdir, output_path, python_exe)


def build_conda(
    wheel_path,
    build_path: Path,
    output_path: Path,
    python_exe: Path,
):
    """
    Convert a wheel file to a conda package.

    Args:
        wheel_path: Path to the wheel file
        build_path: Temporary directory for building
        output_path: Directory where the conda package will be saved
        python_exe: Path to Python executable

    Returns:
        Path to the created conda package
    """
    wheel_path = Path(wheel_path)
    build_path = Path(build_path)
    output_path = Path(output_path)

    # Create build directories
    install_dir = build_path / "install"
    info_dir = install_dir / "info"
    install_dir.mkdir(parents=True, exist_ok=True)
    info_dir.mkdir(parents=True, exist_ok=True)

    # Install wheel to get the files
    install_wheel(wheel_path, install_dir, python_exe)

    # Get distribution metadata
    try:
        # Try to find the installed distribution in site-packages
        python_version = get_python_version_from_executable(python_exe)
        site_packages = install_dir / "lib" / f"python{python_version}" / "site-packages"
        dist_info_dirs = list(site_packages.glob("*.dist-info"))
        if dist_info_dirs:
            distribution = PathDistribution(dist_info_dirs[0])
        else:
            # Fallback: create distribution from wheel metadata
            import zipfile

            with zipfile.ZipFile(wheel_path) as zf:
                metadata_files = [f for f in zf.namelist() if f.endswith("/METADATA")]
                if metadata_files:
                    metadata_content = zf.read(metadata_files[0]).decode("utf-8")
                    distribution = FileDistribution(metadata_content)
                else:
                    raise ValueError(f"No metadata found in wheel: {wheel_path}")

        # Convert to conda metadata
        conda_metadata = CondaMetadata.from_distribution(distribution)

        # Write conda package files
        with open(info_dir / "index.json", "w") as f:
            f.write(json_dumps(conda_metadata.package_record.to_index_json()))

        with open(info_dir / "about.json", "w") as f:
            f.write(json_dumps(conda_metadata.about))

        if conda_metadata.console_scripts:
            with open(info_dir / "link.json", "w") as f:
                f.write(json_dumps(conda_metadata.link_json()))

        # Generate paths.json
        with open(info_dir / "paths.json", "w") as f:
            f.write(json_dumps(paths_json(install_dir)))

        # Create the conda package
        output_path.mkdir(parents=True, exist_ok=True)
        package_stem = conda_metadata.package_record.stem
        conda_package_path = output_path / f"{package_stem}.conda"

        # Remove existing package if it exists
        if conda_package_path.exists():
            conda_package_path.unlink()

        with conda_builder(package_stem, output_path) as builder:
            # Add metadata files from info directory
            for info_file in info_dir.iterdir():
                if info_file.is_file():
                    log.debug(f"Adding info file: info/{info_file.name}")
                    builder.add(str(info_file), arcname=f"info/{info_file.name}")

            # Add package files (everything except info directory)
            for root, dirs, files in os.walk(install_dir):
                # Skip the info directory - it's handled separately above
                if Path(root).name == "info":
                    continue

                for file in files:
                    file_path = Path(root) / file
                    rel_path = file_path.relative_to(install_dir)
                    arcname = rel_path.as_posix()
                    log.debug(f"Adding package file: {arcname}")
                    builder.add(str(file_path), arcname=arcname)

        log.info(f"Created conda package: {conda_package_path}")
        return conda_package_path

    except Exception as e:
        log.error(f"Failed to build conda package from {wheel_path}: {e}")
        raise


def extract_wheel_metadata(wheel_path: Path) -> CondaMetadata:
    """
    Extract metadata from a wheel file without installing it.

    Args:
        wheel_path: Path to the wheel file

    Returns:
        CondaMetadata object with the wheel's metadata
    """
    import zipfile

    with zipfile.ZipFile(wheel_path) as zf:
        # Find METADATA file
        metadata_files = [f for f in zf.namelist() if f.endswith("/METADATA")]
        if not metadata_files:
            raise ValueError(f"No METADATA file found in wheel: {wheel_path}")

        # Read metadata
        metadata_content = zf.read(metadata_files[0]).decode("utf-8")
        distribution = FileDistribution(metadata_content)

        return CondaMetadata.from_distribution(distribution)
