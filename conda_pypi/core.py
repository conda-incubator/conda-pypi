"""
Core conversion functionality for conda-pypi.

This module provides the main high-level functions for converting PyPI packages
to conda format, with and without dependency resolution.
"""

from __future__ import annotations

import configparser
import hashlib
import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable, Optional, Union

import platformdirs
from conda.base.context import context
from conda.cli.main import main_subshell
from conda.core.prefix_data import PrefixData
from conda.exceptions import CondaError
from pip._internal.index.package_finder import PackageFinder

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore

from .utils import (
    ensure_externally_managed,
    get_externally_managed_paths,
    get_package_finder,
    get_python_executable,
    fetch_packages_from_pypi,
    convert_wheels_to_conda,
    pypi_spec_variants,
)
from .solver import PyPIDependencySolver
from .vcs import VCSHandler

log = logging.getLogger(__name__)


def _install_vcs_editable_packages(vcs_packages: list[str], prefix: Union[Path, str]) -> list[str]:
    """
    Install VCS packages in editable mode using pip directly.

    Args:
        vcs_packages: List of VCS URLs (git+https://..., etc.)
        prefix: Conda environment prefix

    Returns:
        List of successfully installed package names
    """

    prefix = Path(prefix)
    python_exe = get_python_executable(prefix)
    installed_packages = []

    for vcs_url in vcs_packages:
        try:
            vcs_info = VCSHandler.parse_vcs_url(vcs_url)
            log.info(f"Installing VCS package in editable mode: {vcs_url}")

            vcs_cache_dir = prefix / "conda-pypi-vcs"
            vcs_cache_dir.mkdir(exist_ok=True)

            url_hash = hashlib.md5(vcs_url.encode()).hexdigest()[:8]
            repo_name = vcs_info.url.split("/")[-1].replace(".git", "")
            persistent_dir = vcs_cache_dir / f"{repo_name}-{url_hash}"

            if persistent_dir.exists():
                shutil.rmtree(persistent_dir)

            repo_path = VCSHandler.clone_repository(vcs_info, persistent_dir)

            cmd = [
                str(python_exe),
                "-m",
                "pip",
                "install",
                "-e",
                str(repo_path),
                "--no-deps",
                "--break-system-packages",
            ]

            subprocess.run(cmd, capture_output=True, text=True, check=True)

            package_name = _extract_package_name_from_source(repo_path)
            if package_name:
                installed_packages.append(package_name)
                log.info(f"Successfully installed VCS package: {package_name}")

        except subprocess.CalledProcessError as e:
            log.error(f"Failed to install VCS package {vcs_url}: {e.stderr}")
        except Exception as e:
            log.error(f"Error installing VCS package {vcs_url}: {e}")

    return installed_packages


def _extract_package_name_from_source(repo_path: Path) -> str:
    """
    Extract package name from Python project source directory.

    Tries pyproject.toml, setup.cfg, then setup.py in order.
    Falls back to directory name if no package name is found.
    """

    pyproject_path = repo_path / "pyproject.toml"
    if pyproject_path.exists():
        try:
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)
                if name := data.get("project", {}).get("name"):
                    return name
        except Exception:
            pass

    setup_cfg_path = repo_path / "setup.cfg"
    if setup_cfg_path.exists():
        try:
            config = configparser.ConfigParser()
            config.read(setup_cfg_path)
            if name := config.get("metadata", "name", fallback=None):
                return name
        except Exception:
            pass

    setup_py_path = repo_path / "setup.py"
    if setup_py_path.exists():
        try:
            content = setup_py_path.read_text()
            if match := re.search(r'name\s*=\s*["\']([^"\']+)["\']', content):
                return match.group(1)
        except Exception:
            pass

    return repo_path.name


def validate_target_env(path: Path, packages: Iterable[str]) -> Iterable[str]:
    """
    Validate that the target environment has the required dependencies
    and filter out already installed packages.
    """
    context.validate_configuration()
    pd = PrefixData(path, pip_interop_enabled=True)

    if not list(pd.query("python>=3.2")):
        raise CondaError(f"Target environment at {path} requires python>=3.2")
    if not list(pd.query("pip>=23.0.1")):
        raise CondaError(f"Target environment at {path} requires pip>=23.0.1")

    packages_to_process = []
    for pkg in packages:
        for spec_variant in pypi_spec_variants(pkg):
            if list(pd.query(spec_variant)):
                print(f"package {pkg} is already installed; ignoring")
                break
        else:
            packages_to_process.append(pkg)

    return packages_to_process


def ensure_target_env_has_externally_managed(command: str):
    """
    Ensure the target environment has EXTERNALLY-MANAGED file for PEP 668 compliance.
    """
    prefix = Path(context.target_prefix)
    externally_managed_paths = get_externally_managed_paths(prefix)

    for path in externally_managed_paths:
        if not path.exists():
            log.info(f"Creating EXTERNALLY-MANAGED file at {path}")
            ensure_externally_managed(path, command)


def convert_packages(
    requested: list[str],
    prefix: Union[Path, str],
    output_dir: Path,
    override_channels: bool = False,
    finder: Optional[PackageFinder] = None,
) -> list[Path]:
    """
    Convert PyPI packages to conda format without installing them.

    This function only converts the explicitly requested packages without
    resolving or converting their dependencies.

    Args:
        requested: List of package names/specs to convert
        prefix: Conda environment prefix (used for Python executable)
        output_dir: Directory where converted .conda packages will be saved
        override_channels: Whether to override default conda channels
        finder: Optional PackageFinder for custom PyPI indices

    Returns:
        List of successfully converted package paths
    """
    prefix = Path(prefix)
    if not prefix.exists():
        raise ValueError(f"Prefix directory does not exist: {prefix}")

    if not finder:
        finder = get_package_finder(prefix)

    python_exe = get_python_executable(prefix)

    with tempfile.TemporaryDirectory() as tmp_path:
        tmp_path = Path(tmp_path)
        wheel_dir = tmp_path / "wheels"
        wheel_dir.mkdir(exist_ok=True)

        fetch_packages_from_pypi(requested, finder, wheel_dir)

        converted_packages = convert_wheels_to_conda(
            wheel_dir, requested, output_dir, python_exe, tmp_path
        )

    return converted_packages


def convert_packages_with_dependencies(
    requested: list[str],
    prefix: Union[Path, str],
    output_dir: Path,
    override_channels: bool = False,
    finder: Optional[PackageFinder] = None,
) -> list[str]:
    """
    Convert PyPI packages to conda format WITH full dependency resolution.

    This function uses the PyPIDependencySolver to automatically discover and convert
    all dependencies needed for the requested packages.

    Args:
        requested: List of package names/specs to convert
        prefix: Conda environment prefix (used for Python executable)
        output_dir: Directory where converted .conda packages will be saved
        override_channels: Whether to override default conda channels
        finder: Optional PackageFinder for custom PyPI indices

    Returns:
        List of package names that were successfully resolved and converted
    """
    solver = PyPIDependencySolver(prefix, override_channels, finder=finder)
    resolved_packages = solver.resolve_dependencies(requested)

    solver_repo = solver.repo / "noarch"
    output_dir.mkdir(parents=True, exist_ok=True)

    copied_packages = []
    for package_name in resolved_packages:
        conda_files = list(solver_repo.glob(f"{package_name}-*.conda"))
        for conda_file in conda_files:
            dest_path = output_dir / conda_file.name
            if not dest_path.exists():
                shutil.copy2(conda_file, dest_path)
                log.info(f"Copied resolved package: {conda_file.name}")
            copied_packages.append(package_name)

    return copied_packages


def prepare_packages_for_installation(
    requested: list[str],
    prefix: Union[Path, str],
    override_channels: bool = False,
    finder: Optional[PackageFinder] = None,
    with_dependencies: bool = True,
    editable: bool = False,
) -> list[str]:
    """
    Prepare packages for installation by converting to conda format or installing directly.

    For editable VCS packages, installs directly with pip. For other packages,
    converts to conda format and caches in persistent pypi channel.

    Args:
        requested: List of package names/specs or VCS URLs
        prefix: Conda environment prefix
        override_channels: Whether to override default conda channels
        finder: Optional PackageFinder for custom PyPI indices
        with_dependencies: Whether to resolve and convert dependencies
        editable: Whether to handle packages as editable installs

    Returns:
        List of package names that were successfully processed
    """
    pypi_channel_dir = Path(platformdirs.user_data_dir("pypi"))

    if editable:
        vcs_packages = [pkg for pkg in requested if VCSHandler.is_vcs_url(pkg)]
        local_packages = [pkg for pkg in requested if not VCSHandler.is_vcs_url(pkg)]

        if vcs_packages:
            _install_vcs_editable_packages(vcs_packages, prefix)

        if local_packages:
            log.info("Local editable installs will be handled directly by pip")

        return []

    if with_dependencies:
        solver = PyPIDependencySolver(
            prefix, override_channels, repo=pypi_channel_dir, finder=finder
        )
        resolved_packages = solver.resolve_dependencies(requested)
        return list(resolved_packages)
    else:
        noarch_dir = pypi_channel_dir / "noarch"
        noarch_dir.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_output = Path(temp_dir)
            converted_packages = convert_packages(
                requested, prefix, temp_output, override_channels, finder
            )

            cached_package_names = []
            for package_path in converted_packages:
                dest_path = noarch_dir / package_path.name
                if not dest_path.exists():
                    shutil.copy2(package_path, dest_path)
                    log.info(f"Cached package: {package_path.name}")
                else:
                    log.info(f"Package already cached: {package_path.name}")

                package_name = package_path.stem.split("-")[0]
                cached_package_names.append(package_name)

        return cached_package_names


def install_packages(
    package_names: list[str],
    prefix: Union[Path, str],
    override_channels: bool = False,
) -> None:
    """
    Install conda packages using conda's solver.

    Args:
        package_names: List of package names to install
        prefix: Conda environment prefix where packages will be installed
        override_channels: Whether to override default conda channels
    """

    cmd_args = ["install", "--prefix", str(prefix), "--yes"]

    if override_channels:
        cmd_args.append("--override-channels")

    pypi_channel_dir = Path(platformdirs.user_data_dir("pypi"))
    cmd_args.extend(["--channel", str(pypi_channel_dir.as_uri())])

    cmd_args.extend(package_names)

    log.info(f"Installing packages: {', '.join(package_names)}")
    main_subshell(*cmd_args)
