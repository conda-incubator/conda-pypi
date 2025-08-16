"""
PyPI dependency resolution using conda's solver.

This module provides the PyPIDependencySolver class that handles iterative
dependency resolution for PyPI packages using conda's LibMambaSolver.
"""

from __future__ import annotations

import logging
import pathlib
import tempfile
from pathlib import Path
from typing import Optional, Union

import platformdirs
import conda.exceptions
from conda.base.context import context
from conda.models.channel import Channel
from conda.models.match_spec import MatchSpec
from conda.exceptions import UnsatisfiableError
from conda_libmamba_solver.solver import LibMambaSolver
from pip._internal.index.package_finder import PackageFinder

from .utils import (
    get_package_finder,
    get_python_short_path,
    update_index,
    fetch_packages_from_pypi,
    convert_wheels_to_conda,
    parse_libmamba_error,
)

log = logging.getLogger(__name__)


class ReloadingLibMambaSolver(LibMambaSolver):
    """
    Reload channels as we add newly converted packages.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.index = None

    def solve_for_diff(self, *args, **kwargs):
        if self.index is not None:
            for channel in self.channels:
                # XXX filter by local channel we update
                self.index.reload_channel(channel)
        return super().solve_for_diff(*args, **kwargs)


class PyPIDependencySolver:
    """
    Handles iterative dependency resolution for PyPI packages using conda's solver.

    This class manages the complex process of:
    1. Trying to solve dependencies with conda's solver
    2. Identifying missing packages from solver errors
    3. Fetching missing packages from PyPI
    4. Converting them to conda format
    5. Repeating until all dependencies are resolved
    """

    def __init__(
        self,
        prefix: Union[pathlib.Path, str],
        override_channels: bool = False,
        repo: Optional[pathlib.Path] = None,
        finder: Optional[PackageFinder] = None,
    ):
        prefix = prefix or context.active_prefix
        if not prefix:
            raise ValueError("prefix is required")
        self.prefix = Path(prefix)
        self.override_channels = override_channels
        self.python_exe = Path(self.prefix, get_python_short_path())

        self.repo = repo or Path(platformdirs.user_data_dir("pypi"))

        if not finder:
            finder = get_package_finder(self.prefix)
        self.finder = finder

    def resolve_dependencies(self, requested: list[str], max_attempts: int = 20) -> set[str]:
        """
        Resolve all dependencies for the requested packages.

        Args:
            requested: List of package names/specs to resolve dependencies for
            max_attempts: Maximum number of resolution attempts

        Returns:
            Set of all package names that were successfully resolved and converted
        """
        (self.repo / "noarch").mkdir(parents=True, exist_ok=True)
        if not (self.repo / "noarch" / "repodata.json").exists():
            update_index(self.repo)

        # Convert string package specs to MatchSpec objects
        requested_specs = [MatchSpec(pkg) for pkg in requested]

        with tempfile.TemporaryDirectory() as tmp_path:
            tmp_path = pathlib.Path(tmp_path)
            repo = self.repo

            WHEEL_DIR = tmp_path / "wheels"
            WHEEL_DIR.mkdir(exist_ok=True)

            prefix = pathlib.Path(self.prefix)
            assert prefix.exists()

            local_channel = Channel(repo.as_uri())

            if not self.override_channels:
                channels = [local_channel, *context.channels]
            else:  # more wheels for us to convert
                channels = [local_channel]

            # Always fetch explicitly requested packages from PyPI first
            fetched_packages = fetch_packages_from_pypi(requested, self.finder, WHEEL_DIR)

            # Convert any fetched wheels to conda packages
            convert_wheels_to_conda(
                WHEEL_DIR, requested, repo / "noarch", self.python_exe, tmp_path
            )
            converted = set(WHEEL_DIR.glob("*.whl"))

            # Update the local channel index with newly converted packages
            update_index(repo)

            solver = ReloadingLibMambaSolver(
                str(prefix),
                channels,
                context.subdirs,
                requested_specs,
                [],
            )

            missing_packages = set()
            attempts = 0
            changes = None
            while attempts < max_attempts:
                attempts += 1
                try:
                    changes = solver.solve_for_diff()
                    break
                except conda.exceptions.PackagesNotFoundError as e:
                    missing_packages = set(e._kwargs["packages"])
                    log.debug(f"Missing packages: {missing_packages}")
                except UnsatisfiableError as e:
                    # parse message
                    log.warning(f"Unsatisfiable: {e}")
                    missing_packages.update(set(parse_libmamba_error(str(e))))

                # Check if there are any new packages to fetch
                new_packages_to_fetch = missing_packages - fetched_packages
                if not new_packages_to_fetch:
                    log.debug("No new packages to fetch, breaking retry loop")
                    break

                # Fetch any missing dependencies from PyPI
                new_fetched = fetch_packages_from_pypi(
                    sorted(new_packages_to_fetch), self.finder, WHEEL_DIR
                )
                fetched_packages.update(new_fetched)

                # Convert any newly fetched dependency wheels
                new_wheels = [w for w in WHEEL_DIR.glob("*.whl") if w not in converted]
                if new_wheels:
                    convert_wheels_to_conda(
                        WHEEL_DIR, requested, repo / "noarch", self.python_exe, tmp_path
                    )
                    converted.update(new_wheels)

                update_index(repo)
            else:
                log.error(f"Exceeded maximum of {max_attempts} attempts")
                raise RuntimeError(f"Could not resolve dependencies after {max_attempts} attempts")

            if changes is None:
                log.error("No solution found - environment solving failed")
                raise RuntimeError("No solution found - environment solving failed")

            log.info(f"Solution: {changes}")
            log.info(
                f"Dependency resolution completed. Packages available in local channel: {repo.as_uri()}"
            )

            # Return the names of all packages that were fetched and converted
            return fetched_packages
