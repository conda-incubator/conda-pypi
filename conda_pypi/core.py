"""
Core conversion functionality for conda-pypi.

This module provides the main high-level functions for converting PyPI packages
to conda format, with and without dependency resolution.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path
from typing import Iterable, Optional, Union

import platformdirs
from conda.base.context import context
from conda.core.prefix_data import PrefixData
from conda.exceptions import CondaError
from pip._internal.index.package_finder import PackageFinder

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

log = logging.getLogger(__name__)


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
                log.warning("package %s is already installed; ignoring", pkg)
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
) -> list[str]:
    """
    Convert PyPI packages to conda format and cache them in the persistent pypi channel.

    This function is designed for the install workflow - it converts packages and
    caches them in a persistent location for efficient installation.

    Args:
        requested: List of package names/specs to convert
        prefix: Conda environment prefix (used for Python executable)
        override_channels: Whether to override default conda channels
        finder: Optional PackageFinder for custom PyPI indices
        with_dependencies: Whether to resolve and convert dependencies (default: True)

    Returns:
        List of package names that were successfully converted and cached
    """
    pypi_channel_dir = Path(platformdirs.user_data_dir("pypi"))

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
    from conda.cli.main import main_subshell

    cmd_args = ["install", "--prefix", str(prefix), "--yes"]

    if override_channels:
        cmd_args.append("--override-channels")

    pypi_channel_dir = Path(platformdirs.user_data_dir("pypi"))
    cmd_args.extend(["--channel", str(pypi_channel_dir.as_uri())])

    cmd_args.extend(package_names)

    log.info(f"Installing packages: {', '.join(package_names)}")
    main_subshell(*cmd_args)
