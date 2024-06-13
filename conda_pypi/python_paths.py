"""
Logic to place and find Python paths and EXTERNALLY-MANAGED in target (conda) environments.

Since functions in this module might be called to facilitate installation of the package,
this module MUST only use the Python stdlib. No 3rd party allowed (except for importlib-resources).
"""

import os
import sys
import sysconfig
from logging import getLogger
from pathlib import Path
from subprocess import check_output
from typing import Iterator

try:
    from importlib.resources import files as importlib_files
except ImportError:  # python <3.9
    from importlib_resources import files as importlib_files


logger = getLogger(f"conda.{__name__}")


def get_env_python(prefix: os.PathLike = None) -> Path:
    prefix = Path(prefix or sys.prefix)
    if os.name == "nt":
        return prefix / "python.exe"
    return prefix / "bin" / "python"


def _get_env_sysconfig_path(key: str, prefix: os.PathLike = None) -> Path:
    prefix = Path(prefix or sys.prefix)
    if str(prefix) == sys.prefix:
        return Path(sysconfig.get_path(key), sysconfig.get_default_scheme())
    return Path(
        check_output(
            [
                get_env_python(prefix),
                "-c",
                f"import sysconfig; sysconfig.get_path('{key}', sysconfig.get_default_scheme())",
            ],
            text=True,
        ).strip()
    )


def get_env_stdlib(prefix: os.PathLike = None) -> Path:
    return _get_env_sysconfig_path("stdlib", prefix)


def get_env_site_packages(prefix: os.PathLike = None) -> Path:
    return _get_env_sysconfig_path("purelib", prefix)


def get_current_externally_managed_path(prefix: os.PathLike = None) -> Path:
    """
    Returns the path for EXTERNALLY-MANAGED for the given Python installation in 'prefix'.
    Not guaranteed to exist. There might be more EXTERNALLY-MANAGED files in 'prefix' for
    older Python versions. These are not returned.
    """
    prefix = Path(prefix or sys.prefix)
    return get_env_stdlib(prefix) / "EXTERNALLY-MANAGED"


def get_externally_managed_paths(prefix: os.PathLike = None) -> Iterator[Path]:
    """
    Returns all the possible EXTERNALLY-MANAGED paths in 'prefix', for all found
    Python installations. The paths themselves are not guaranteed to exist.
    """
    prefix = Path(prefix or sys.prefix)
    if os.name == "nt":
        yield get_current_externally_managed_path(prefix)
    else:
        for python_dir in sorted(Path(prefix, "lib").glob("python*")):
            if python_dir.is_dir():
                yield Path(python_dir, "EXTERNALLY-MANAGED")


def ensure_externally_managed(prefix: os.PathLike = None) -> Path:
    """
    conda-pypi places its own EXTERNALLY-MANAGED file when it is installed in an environment.
    We also need to place it in _new_ environments created by conda. We do this by implementing
    some extra plugin hooks.
    """
    target_path = next(get_current_externally_managed_path(prefix))
    if target_path.exists():
        return target_path
    logger.info("Placing EXTERNALLY-MANAGED in %s", target_path.parent)
    resource = importlib_files("conda_pypi") / "data" / "EXTERNALLY-MANAGED"
    target_path.write_text(resource.read_text())
    return target_path
