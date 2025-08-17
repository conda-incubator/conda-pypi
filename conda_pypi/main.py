"""
Main functionality for conda-pypi
"""

from __future__ import annotations

import os
from logging import getLogger
from pathlib import Path
from typing import Iterable

from conda.base.context import context
from conda.core.prefix_data import PrefixData
from conda.history import History
from conda.exceptions import CondaError

from .utils import ensure_externally_managed, get_externally_managed_paths, pypi_spec_variants

logger = getLogger(f"conda.{__name__}")


def validate_target_env(path: Path, packages: Iterable[str]) -> Iterable[str]:
    """
    Validate that the target environment has the required dependencies
    and filter out already installed packages.
    """

    context.validate_configuration()
    pd = PrefixData(path, interoperability=True)

    if not list(pd.query("python>=3.2")):
        raise CondaError(f"Target environment at {path} requires python>=3.2")
    if not list(pd.query("pip>=23.0.1")):
        raise CondaError(f"Target environment at {path} requires pip>=23.0.1")

    packages_to_process = []
    for pkg in packages:
        # Check all variants of the package name (with dashes and underscores)
        for spec_variant in pypi_spec_variants(pkg):
            if list(pd.query(spec_variant)):
                print(f"package {pkg} is already installed; ignoring")
                break
        else:
            packages_to_process.append(pkg)

    return packages_to_process


def ensure_target_env_has_externally_managed(command: str):
    """
    post-command hook to ensure that the target env has the EXTERNALLY-MANAGED file
    even when it is created by conda, not 'conda-pypi'.
    """
    if os.environ.get("CONDA_BUILD_STATE") == "BUILD":
        return
    base_prefix = Path(context.conda_prefix)
    target_prefix = Path(context.target_prefix)
    if base_prefix == target_prefix or base_prefix.resolve() == target_prefix.resolve():
        return
    requested_specs_map = History(base_prefix).get_requested_specs_map()
    if requested_specs_map and "conda-pypi" not in requested_specs_map:
        return
    prefix_data = PrefixData(target_prefix)
    if command in {"create", "install", "update"}:
        if not list(prefix_data.query("pip")):
            return
        if command != "create" and os.name != "nt":
            for path in get_externally_managed_paths(target_prefix):
                if path.exists():
                    path.unlink()
        ensure_externally_managed(target_prefix)
    elif command == "remove":
        if list(prefix_data.query("pip")):
            # leave in place if pip is still installed
            return
        for path in get_externally_managed_paths(target_prefix):
            if path.exists():
                path.unlink()
    else:
        raise ValueError(f"command {command} not recognized.")
