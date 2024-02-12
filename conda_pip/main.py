import os
import sys
import sysconfig
from logging import getLogger
from pathlib import Path
from subprocess import run, check_output
from typing import Iterable

try:
    from importlib.resources import files as importlib_files
except ImportError:
    from importlib_resources import files as importlib_files

from conda.history import History
from conda.base.context import context, locate_prefix_by_name
from conda.core.prefix_data import PrefixData
from conda.cli.python_api import run_command
from conda.exceptions import CondaError, CondaSystemExit
from conda.models.match_spec import MatchSpec

logger = getLogger(f"conda.{__name__}")
HERE = Path(__file__).parent.resolve()


def get_prefix(prefix: os.PathLike = None, name: str = None) -> Path:
    if prefix:
        return Path(prefix)
    elif name:
        return Path(locate_prefix_by_name(name))
    else:
        return Path(context.target_prefix)


def get_env_python(prefix: os.PathLike = None) -> Path:
    prefix = Path(prefix or sys.prefix)
    if os.name == "nt":
        return prefix / "python.exe"
    return prefix / "bin" / "python"


def get_env_stdlib(prefix: os.PathLike = None) -> Path:
    prefix = Path(prefix or sys.prefix)
    if str(prefix) == sys.prefix:
        return Path(sysconfig.get_path("stdlib"))
    return Path(check_output([get_env_python(prefix), "-c", "import sysconfig; print(sysconfig.get_paths()['stdlib'])"], text=True).strip())


def get_externally_managed_path(prefix: os.PathLike = None) -> Path:
    prefix = Path(prefix or sys.prefix)
    if os.name == "nt":
        yield Path(prefix, "Lib", "EXTERNALLY-MANAGED")
    else:
        found = False
        for python_dir in sorted(Path(prefix, "lib").glob("python*")):
            if python_dir.is_dir():
                found = True
                yield Path(python_dir, "EXTERNALLY-MANAGED")
        if not found:
            raise ValueError("Could not locate EXTERNALLY-MANAGED file")


def validate_target_env(path: Path, packages: Iterable[str]) -> Iterable[str]:
    context.validate_configuration()
    pd = PrefixData(path, pip_interop_enabled=True)

    if not list(pd.query("python>=3.2")):
        raise CondaError(f"Target environment at {path} requires python>=3.2")
    if not list(pd.query("pip>=23.0.1")):
        raise CondaError(f"Target environment at {path} requires pip>=23.0.1")

    packages_to_process = []
    for pkg in packages:
        spec = MatchSpec(pkg)
        if list(pd.query(spec)):
            logger.warning("package %s is already installed; ignoring", spec)
            continue
        packages_to_process.append(pkg)
    return packages_to_process


def run_conda_install(
    prefix: Path,
    specs: Iterable[MatchSpec],
    dry_run=False,
    quiet=False,
    verbosity=0,
    force_reinstall=False,
    yes=False,
    json=False,
):
    if not specs:
        return 0

    command = ["install", "--prefix", str(prefix)]
    if dry_run:
        command.append("--dry-run")
    if quiet:
        command.append("--quiet")
    if verbosity:
        command.append("-" + ("v" * verbosity))
    if force_reinstall:
        command.append("--force-reinstall")
    if yes:
        command.append("--yes")
    if json:
        command.append("--json")

    command.extend(str(spec) for spec in specs)

    logger.info("conda install command: conda %s", command)
    try:
        *_, retcode = run_command(*command, stdout=None, stderr=None, use_exception_handler=True)
    except CondaSystemExit:
        return 0
    return retcode


def run_pip_install(
    prefix: Path,
    specs,
    upgrade=False,
    dry_run=False,
    quiet=False,
    verbosity=0,
    force_reinstall=False,
    yes=False,
):
    if not specs:
        return 0
    command = [
        get_env_python(prefix),
        "-mpip",
        "install",
        "--no-deps",
        "--prefix",
        str(prefix),
    ]
    if dry_run:
        command.append("--dry-run")
    if quiet:
        command.append("--quiet")
    if verbosity:
        command.append("-" + ("v" * verbosity))
    if force_reinstall:
        command.append("--force-reinstall")
    if upgrade:
        command.append("--upgrade")
    command.extend(specs)

    logger.info("pip install command: %s", command)
    process = run(command)
    return process.returncode


def ensure_externally_managed(prefix: os.PathLike = None) -> Path:
    """
    conda-pip places its own EXTERNALLY-MANAGED file when it is installed in an environment.
    We also need to place it in _new_ environments created by conda. We do this by implementing
    some extra plugin hooks.
    """
    target_path = next(get_externally_managed_path(prefix))
    if target_path.exists():
        return target_path
    logger.info("Placing EXTERNALLY-MANAGED in %s", target_path.parent)
    resource = importlib_files("conda_pip") / "data" / "EXTERNALLY-MANAGED"
    target_path.write_text(resource.read_text())
    return target_path


def ensure_target_env_has_externally_managed(command: str):
    """
    post-command hook to ensure that the target env has the EXTERNALLY-MANAGED file
    even when it is created by conda, not 'conda-pip'.
    """
    if os.environ.get("CONDA_BUILD_STATE") == "BUILD":
        return
    base_prefix = Path(context.conda_prefix)
    target_prefix = Path(context.target_prefix)
    if base_prefix == target_prefix:
        return
    # ensure conda-pip was explicitly installed in base env (and not as a dependency)
    requested_specs_map = History(base_prefix).get_requested_specs_map()
    if requested_specs_map and "conda-pip" not in requested_specs_map:
        return
    prefix_data = PrefixData(target_prefix)
    if command in {"create", "install", "update"}:
        # ensure target env has pip installed
        if not list(prefix_data.query("pip")):
            return
        # Check if there are some leftover EXTERNALLY-MANAGED files from other Python versions
        if command != "create" and os.name != "nt":
            for path in get_externally_managed_path(target_prefix):
                if path.exists():
                    path.unlink()
        ensure_externally_managed(target_prefix)
    elif command == "remove":
        if list(prefix_data.query("pip")):
            # leave in place if pip is still installed
            return
        for path in get_externally_managed_path(target_prefix):
            if path.exists():
                path.unlink()
    else:
        raise ValueError(f"command {command} not recognized.")
