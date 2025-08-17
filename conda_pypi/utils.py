"""
Consolidated utilities for conda-pypi.

This module contains all utility functions including:
- PyPI package fetching and downloading
- Path utilities and Python executable detection
- Channel index management
- Package name variants and specifications
- Helper functions for package conversion
"""

from __future__ import annotations

import hashlib
import os
import pkgutil
import re
import subprocess
import sys
from enum import Enum
from logging import getLogger
from os.path import isfile, islink
from pathlib import Path
from typing import Iterator, Optional, List

import conda.common.path
from conda.base.context import context, locate_prefix_by_name
from conda.core.prefix_data import get_python_version_for_prefix
from conda.gateways.connection.download import download
from conda.models.match_spec import MatchSpec
from conda_index.index import ChannelIndex
from pip._internal.index.collector import LinkCollector
from pip._internal.index.package_finder import PackageFinder
from pip._internal.models.search_scope import SearchScope
from pip._internal.models.selection_prefs import SelectionPreferences
from pip._internal.models.target_python import TargetPython
from pip._internal.network.session import PipSession

from .exceptions import PypiError

# Lazy imports to avoid circular dependencies
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = getLogger(f"conda.{__name__}")


class PathType(Enum):
    """
    Refers to if the file in question is hard linked or soft linked. Originally
    designed to be used in paths.json
    """

    hardlink = "hardlink"
    softlink = "softlink"
    directory = "directory"  # rare or unused?

    # these additional types should not be included by conda-build in packages
    linked_package_record = "linked_package_record"  # a package's .json file in conda-meta
    pyc_file = "pyc_file"
    unix_python_entry_point = "unix_python_entry_point"
    windows_python_entry_point_script = "windows_python_entry_point_script"
    windows_python_entry_point_exe = "windows_python_entry_point_exe"

    def __str__(self):
        return self.name

    def __json__(self):
        return self.name


def sha256_checksum(filename, entry: Optional[os.DirEntry] = None, buffersize=1 << 18):
    """Calculate SHA256 checksum of a file."""

    if not entry:
        is_link = islink(filename)
        is_file = isfile(filename)
    else:
        is_link = entry.is_symlink()
        is_file = entry.is_file()
    if is_link and not is_file:
        # symlink to nowhere so an empty file
        # this is the sha256 hash of an empty file
        return "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    if not is_file:
        return None
    sha256 = hashlib.sha256()
    with open(filename, "rb") as f:
        for block in iter(lambda: f.read(buffersize), b""):
            sha256.update(block)
    return sha256.hexdigest()


# =============================================================================
# Path Utilities
# =============================================================================


def get_prefix(prefix: os.PathLike = None, name: str = None) -> Path:
    """Get the conda environment prefix path."""
    if prefix:
        return Path(prefix)
    elif name:
        return Path(locate_prefix_by_name(name))
    else:
        return Path(context.target_prefix)


def get_python_short_path():
    """Get the short path to Python executable within a conda environment."""

    return conda.common.path.get_python_short_path()


def get_python_executable(prefix: Path):
    """Get the full path to Python executable in the given prefix."""
    return Path(prefix, get_python_short_path())


def get_externally_managed_paths(prefix: Path) -> List[Path]:
    """
    Get paths where EXTERNALLY-MANAGED files should be placed for PEP 668 compliance.

    Returns all the possible EXTERNALLY-MANAGED paths in 'prefix', for all found
    Python (former) installations. The paths themselves are not guaranteed to exist.

    This does NOT invoke python's sysconfig because Python might not be installed (anymore).

    Args:
        prefix: Conda environment prefix

    Returns:
        List of paths where EXTERNALLY-MANAGED files should be placed
    """
    prefix = Path(prefix)
    paths = []

    if os.name == "nt":
        paths.append(prefix / "Lib" / "EXTERNALLY-MANAGED")
    else:
        for python_dir in sorted(Path(prefix, "lib").glob("python*")):
            if python_dir.is_dir():
                paths.append(Path(python_dir, "EXTERNALLY-MANAGED"))

    return paths


def ensure_externally_managed(path_or_prefix):
    """
    Ensure EXTERNALLY-MANAGED file exists for PEP 668 compliance.

    Args:
        path_or_prefix: Either a direct path to EXTERNALLY-MANAGED file or a prefix
    """
    if isinstance(path_or_prefix, (str, Path)):
        path_or_prefix = Path(path_or_prefix)

        # If it's a directory (prefix), get the EXTERNALLY-MANAGED paths
        if path_or_prefix.is_dir():
            paths = get_externally_managed_paths(path_or_prefix)
        else:
            paths = [path_or_prefix]
    else:
        paths = [path_or_prefix]

    template = pkgutil.get_data("conda_pypi", "data/EXTERNALLY-MANAGED")
    if not template:
        raise RuntimeError("EXTERNALLY-MANAGED template not found. Package may be corrupted.")
    content = template.decode("utf-8")

    for path in paths:
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            logger.info(f"Created EXTERNALLY-MANAGED file at {path}")


def get_env_python(prefix: Path) -> Path:
    """
    Get the path to the Python executable in the given environment.

    Args:
        prefix: Path to the conda environment

    Returns:
        Path to the Python executable
    """
    return get_python_executable(prefix)


def get_env_stdlib(prefix: Path) -> Path:
    """
    Get the path to the standard library directory in the given environment.

    Args:
        prefix: Path to the conda environment

    Returns:
        Path to the standard library directory
    """

    python_exe = get_python_executable(prefix)

    try:
        # Get the stdlib directory using the prefix's Python
        result = subprocess.run(
            [str(python_exe), "-c", "import sysconfig; print(sysconfig.get_paths()['stdlib'])"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fallback: construct manually
        version_info = sys.version_info
        return prefix / "lib" / f"python{version_info.major}.{version_info.minor}"


def get_env_site_packages(prefix: Path) -> Path:
    """
    Get the path to the site-packages directory in the given environment.

    Args:
        prefix: Path to the conda environment

    Returns:
        Path to the site-packages directory
    """

    python_exe = get_python_executable(prefix)

    try:
        # Get the site-packages directory using the prefix's Python
        result = subprocess.run(
            [str(python_exe), "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fallback: construct manually
        version_info = sys.version_info
        return (
            prefix / "lib" / f"python{version_info.major}.{version_info.minor}" / "site-packages"
        )


# =============================================================================
# Package Specification Utilities
# =============================================================================


def pypi_spec_variants(spec_str: str) -> Iterator[str]:
    """Generate variants of a package specification with different name formats."""
    yield spec_str
    spec = MatchSpec(spec_str)
    seen = {spec_str}
    for name_variant in (
        spec.name.replace("-", "_"),
        spec.name.replace("_", "-"),
    ):
        if name_variant not in seen:  # only yield if actually different
            yield str(MatchSpec(spec, name=name_variant))
            seen.add(name_variant)


def extract_package_name_from_spec(package_spec) -> str:
    """
    Extract the base package name from a package specification.

    Examples:
        'requests>=2.0' -> 'requests'
        'numpy==1.21.0' -> 'numpy'
        'scipy' -> 'scipy'
    """
    # Handle both string specs and MatchSpec objects
    if hasattr(package_spec, "name"):
        # It's a MatchSpec object
        return package_spec.name

    # It's a string spec
    # Remove version constraints and extras
    name = package_spec.split("[")[0]  # Remove extras like package[extra]
    name = re.split(r"[<>=!]", name)[0]  # Remove version constraints
    return name.strip()


# =============================================================================
# PyPI Package Fetching
# =============================================================================


def get_package_finder(prefix: Path) -> PackageFinder:
    """
    Create a PackageFinder with the prefix's Python version, not our Python.
    """

    py_ver = get_python_version_for_prefix(prefix)
    if not py_ver:
        raise PypiError(f"Python not found in {prefix}")
    py_version_info = tuple(map(int, py_ver.split(".")))
    target_python = TargetPython(py_version_info=py_version_info)

    # Create a session and link collector
    session = PipSession()
    # Include PyPI index URL
    index_urls = ["https://pypi.org/simple/"]
    search_scope = SearchScope.create(find_links=[], index_urls=index_urls, no_index=False)
    link_collector = LinkCollector(session=session, search_scope=search_scope)

    # Create selection preferences
    selection_prefs = SelectionPreferences(allow_yanked=False)

    return PackageFinder.create(
        link_collector=link_collector,
        selection_prefs=selection_prefs,
        target_python=target_python,
    )


def find_package(finder: PackageFinder, package: str):
    """
    Convert package to MatchSpec and return best Link from PyPI.
    """
    from .builder import conda_to_requires

    spec = MatchSpec(package)  # type: ignore # metaclass confuses type checker
    requirement = conda_to_requires(spec)
    if not requirement:
        raise RuntimeError(f"Could not convert {package} to Python Requirement()!")

    # Use find_best_candidate instead of find_best_match
    logger.debug(f"Finding package {requirement.name} with specifier {requirement.specifier}")
    candidates = finder.find_best_candidate(requirement.name, requirement.specifier)
    logger.debug(f"Found candidates: {candidates}")
    return candidates


def find_and_fetch(finder: PackageFinder, target: Path, package: str):
    """
    Find package on PyPI and download best link to target directory.
    """
    candidates = find_package(finder, package)
    if not candidates or not candidates.best_candidate:
        raise PypiError(f"No PyPI link for {package}")

    link = candidates.best_candidate.link
    filename = link.url_without_fragment.rsplit("/", 1)[-1]
    logger.info(f"Fetching {package} as {filename}")
    download(link.url, target / filename)


def fetch_packages_from_pypi(
    requested: list[str], finder: PackageFinder, wheel_dir: Path
) -> set[str]:
    """
    Fetch packages from PyPI into the specified wheel directory.

    Args:
        requested: List of package names/specs to fetch
        finder: PackageFinder for locating packages
        wheel_dir: Directory to save downloaded wheels

    Returns:
        Set of package names that were successfully fetched
    """
    fetched_packages = set()

    for package in requested:
        try:
            find_and_fetch(finder, wheel_dir, package)
            package_name = extract_package_name_from_spec(package)
            fetched_packages.add(package_name)
            logger.info(f"Successfully fetched: {package}")
        except Exception as e:
            logger.warning(f"Failed to fetch {package}: {e}")
            # Continue with other packages even if one fails

    return fetched_packages


# =============================================================================
# Package Conversion Utilities
# =============================================================================


def convert_wheels_to_conda(
    wheel_dir: Path, requested: list[str], output_dir: Path, python_exe: Path, tmp_path: Path
) -> list[Path]:
    """
    Convert wheel files to conda packages using conda-pypi build functionality.

    Args:
        wheel_dir: Directory containing wheel files
        requested: List of originally requested packages (for logging)
        output_dir: Directory where conda packages will be saved
        python_exe: Path to Python executable
        tmp_path: Temporary directory for intermediate files

    Returns:
        List of paths to successfully converted conda packages
    """
    from .builder import build_conda

    converted_packages = []
    wheel_files = list(wheel_dir.glob("*.whl"))

    if not wheel_files:
        logger.warning("No wheel files found to convert")
        return converted_packages

    for wheel_file in wheel_files:
        try:
            logger.info(f"Converting wheel to conda: {wheel_file.name}")

            # Create a temporary build directory for this wheel
            build_dir = tmp_path / f"build_{wheel_file.stem}"
            build_dir.mkdir(exist_ok=True)

            # Convert wheel to conda package
            conda_package_path = build_conda(wheel_file, build_dir, output_dir, python_exe)

            if conda_package_path and conda_package_path.exists():
                converted_packages.append(conda_package_path)
                logger.info(f"Successfully converted: {conda_package_path.name}")
            else:
                logger.warning(f"Failed to convert {wheel_file.name}: no output file")

        except Exception as e:
            logger.error(f"Error converting {wheel_file.name}: {e}")
            # Continue with other wheels even if one fails

    logger.info(f"Converted {len(converted_packages)} out of {len(wheel_files)} wheels")
    return converted_packages


# =============================================================================
# Channel Index Management
# =============================================================================


def update_index(path: Path):
    """
    Update the conda channel index at the specified path.
    """
    channel_index = ChannelIndex(
        path,
        None,
        threads=1,
        debug=False,
        write_bz2=False,
        write_zst=True,
        write_run_exports=True,
        compact_json=True,
        write_current_repodata=False,
    )
    channel_index.index(patch_generator=None)
    channel_index.update_channeldata()


# =============================================================================
# Error Parsing Utilities
# =============================================================================


def parse_libmamba_error(message: str):
    """
    Parse missing packages out of LibMambaUnsatisfiableError message.
    """
    # Extract package names from error messages
    # This is a simplified parser - may need enhancement for complex cases
    packages = []
    lines = message.split("\n")
    for line in lines:
        if "package" in line.lower() and (
            "not found" in line.lower() or "missing" in line.lower()
        ):
            # Try to extract package name from the line
            words = line.split()
            for word in words:
                if word.replace("-", "").replace("_", "").isalnum():
                    packages.append(word)
                    break
    return packages
