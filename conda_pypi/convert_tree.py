"""
Convert a dependency tree from pypi into .conda packages
"""

from __future__ import annotations

import logging
import pathlib
import re
import tempfile
from pathlib import Path
from typing import Iterable, Optional, Union

import conda.exceptions
import platformdirs
from conda.base.context import context
from conda.common.path import get_python_short_path
from conda.models.channel import Channel
from conda.models.match_spec import MatchSpec
from conda_libmamba_solver.solver import (
    LibMambaIndexHelper,
    LibMambaSolver,
    LibMambaUnsatisfiableError,
    SolverInputState,
)
from unearth import PackageFinder

from conda_pypi.build import build_conda
from conda_pypi.downloader import find_and_fetch, get_package_finder
from conda_pypi.index import update_index

log = logging.getLogger(__name__)

NOTHING_PROVIDES_RE = re.compile(r"nothing provides (.*) needed by")


def parse_libmamba_error(message: str):
    """
    Parse missing packages out of LibMambaUnsatisfiableError message.
    """
    for line in message.splitlines():
        if match := NOTHING_PROVIDES_RE.search(line):
            yield match.group(1)


class ReloadingLibMambaSolver(LibMambaSolver):
    """
    Reload channels as we add newly converted packages.
    LibMambaIndexHelper appears to be addressing C++ singletons or global state.
    """

    def _collect_all_metadata(
        self,
        channels: Iterable[Channel],
        conda_build_channels: Iterable[Channel],
        subdirs: Iterable[str],
        in_state: SolverInputState,
    ) -> LibMambaIndexHelper:
        index = LibMambaIndexHelper(
            channels=[*conda_build_channels, *channels],
            subdirs=subdirs,
            repodata_fn=self._repodata_fn,
            installed_records=(
                *in_state.installed.values(),
                *in_state.virtual.values(),
            ),
            pkgs_dirs=context.pkgs_dirs if context.offline else (),
        )
        for channel in channels:
            # XXX filter by local channel we update
            index.reload_channel(channel)
        return index


class ConvertTree:
    def __init__(
        self,
        prefix: Optional[Union[pathlib.Path, str]],
        override_channels=False,
        repo: Optional[pathlib.Path] = None,
        finder: Optional[PackageFinder] = None,  # to change index_urls e.g.
    ):
        # platformdirs location has a space in it; ok?
        # will be expanded to %20 in "as uri" output, conda understands that.
        self.repo = repo or Path(platformdirs.user_data_dir("pypi"))
        prefix = prefix or context.active_prefix
        if not prefix:
            raise ValueError("prefix is required")
        self.prefix = Path(prefix)
        self.override_channels = override_channels
        self.python_exe = Path(self.prefix, get_python_short_path())

        if not finder:
            finder = self.default_package_finder()
        self.finder = finder

    def default_package_finder(self):
        return get_package_finder(self.prefix)

    def convert_tree(self, requested: list[str], max_attempts=20):
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

            solver = ReloadingLibMambaSolver(
                str(prefix),
                channels,
                context.subdirs,
                requested_specs,
                [],
            )

            converted = set()
            fetched_packages = set()
            missing_packages = set()
            attempts = 0
            while len(fetched_packages) < max_attempts and attempts < max_attempts:
                attempts += 1
                try:
                    changes = solver.solve_for_diff()
                    break
                except conda.exceptions.PackagesNotFoundError as e:
                    missing_packages = set(e._kwargs["packages"])
                    log.debug(f"Missing packages: {missing_packages}")
                except LibMambaUnsatisfiableError as e:
                    # parse message
                    log.warning(f"Unsatisfiable: {e}")
                    missing_packages.update(set(parse_libmamba_error(e.message)))

                for package in sorted(missing_packages - fetched_packages):
                    find_and_fetch(self.finder, WHEEL_DIR, package)
                    fetched_packages.add(package)

                for normal_wheel in WHEEL_DIR.glob("*.whl"):
                    if normal_wheel in converted:
                        continue

                    log.info(f"Converting {normal_wheel}")

                    build_path = tmp_path / normal_wheel.stem
                    build_path.mkdir()

                    try:
                        package_conda = build_conda(
                            normal_wheel,
                            build_path,
                            repo / "noarch",  # XXX could be arch
                            self.python_exe,
                            is_editable=False,
                        )
                        log.info(f"Conda package created at {package_conda}")
                    except FileExistsError:
                        log.info(
                            f"Tried to convert wheel that is already conda-ized: {normal_wheel}"
                        )

                    converted.add(normal_wheel)

                update_index(repo)
            else:
                log.error(f"Exceeded maximum of {max_attempts} attempts")
                return

            log.info(f"Solution: {changes}")

            # Install the packages using the solver's solution
            if changes:
                from conda.cli.main import main_subshell

                log.info(f"Installing packages from local channel: {repo.as_uri()}")
                try:
                    # Install the originally requested packages from the local channel
                    # The solver has already resolved dependencies, so we install what was requested
                    install_args = ["install", "--prefix", str(prefix), "-c", repo.as_uri(), "-y"]

                    # Configure channels based on override_channels setting
                    if not self.override_channels:
                        # Include configured channels for dependencies not in our local channel
                        # Skip the first channel (local_channel) and add the rest
                        for channel in channels[1:]:
                            # Handle both Channel objects and strings
                            channel_name = getattr(channel, "canonical_name", str(channel))
                            install_args.extend(["-c", channel_name])
                    else:
                        # Only use our local channel
                        install_args.append("--override-channels")

                    install_args.extend(requested)
                    main_subshell(*install_args)
                    log.info("Installation completed successfully")
                except Exception as e:
                    log.error(f"Installation failed: {e}")
                    fallback_cmd = f"conda install -c {repo.as_uri()}"
                    if not self.override_channels:
                        # Include configured channels for dependencies not in our local channel
                        for channel in channels[1:]:
                            # Handle both Channel objects and strings
                            channel_name = getattr(channel, "canonical_name", str(channel))
                            fallback_cmd += f" -c {channel_name}"
                    else:
                        fallback_cmd += " --override-channels"
                    fallback_cmd += f" {' '.join(requested)}"
                    log.info(f"Manual installation: {fallback_cmd}")
            else:
                log.info("No changes to install - all packages may already be satisfied")
