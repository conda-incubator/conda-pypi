import os
import shutil
from logging import getLogger
from pathlib import Path
from subprocess import run, check_output
from typing import Iterable

from conda.base.context import context, locate_prefix_by_name
from conda.core.prefix_data import PrefixData
from conda.cli.python_api import run_command
from conda.exceptions import CondaError, CondaSystemExit
from conda.models.match_spec import MatchSpec

logger = getLogger(f"conda.{__name__}")
HERE = Path(__file__).parent.resolve()


def get_prefix(prefix: Path = None, name: str =None):
    if prefix:
        return prefix
    elif name:
        return locate_prefix_by_name(name)
    else:
        return context.target_prefix

def get_env_python(prefix: Path):
    if os.name == "nt":
        return prefix / "python.exe"
    return prefix / "bin" / "python"

def validate_target_env(path: Path, packages: Iterable[str]) -> Iterable[str]:
    context.validate_configuration()
    pd = PrefixData(path, pip_interop_enabled=True)

    if not list(pd.query("python")):
        raise CondaError(f"Target environment at {path} does not have Python installed")
    if not list(pd.query("pip")):
        raise CondaError(f"Target environment at {path} does not have pip installed")

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
    if yes:
        command.append("--yes")
    if upgrade:
        command.append("--upgrade")
    command.extend(specs)

    logger.info("pip install command: %s", command)
    process = run(command)
    if process.returncode:
        return process.returncode


def place_externally_managed(prefix: Path):
    """
    conda-pip places its own EXTERNALLY-MANAGED file when it is installed in an environment.
    We also need to place it in _new_ environments created by conda. We do this by implementing
    some extra plugin hooks.
    """
    # Get target env stdlib path
    base_dir = check_output([get_env_python(prefix), "-c", "import sysconfig; print(sysconfig.get_path('stdlib', sysconfig.get_default_scheme()))"], text=True)
    base_dir = base_dir.strip()
    externally_managed = Path(base_dir, "EXTERNALLY-MANAGED")
    if externally_managed.exists():
        return
    logger.info("placing EXTERNALLY-MANAGED in %s", base_dir)
    shutil.copy(HERE / "data" / "EXTERNALLY-MANAGED", externally_managed)
