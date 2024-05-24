from __future__ import annotations

import json
import os
import shlex
import sys
from logging import getLogger
from pathlib import Path
from subprocess import run, CompletedProcess
from tempfile import NamedTemporaryFile
from typing import Any, Iterable, Literal

try:
    from importlib.resources import files as importlib_files
except ImportError:
    from importlib_resources import files as importlib_files


from conda.base.context import context
from conda.core.prefix_data import PrefixData
from conda.gateways.disk.read import compute_sum
from conda.models.enums import PackageType
from conda.history import History
from conda.cli.python_api import run_command
from conda.exceptions import CondaError, CondaSystemExit
from conda.models.match_spec import MatchSpec

from .utils import (
    get_env_python,
    get_env_site_packages,
    get_externally_managed_path,
    pypi_spec_variants,
)

logger = getLogger(f"conda.{__name__}")
HERE = Path(__file__).parent.resolve()


def validate_target_env(path: Path, packages: Iterable[str]) -> Iterable[str]:
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
                logger.warning("package %s is already installed; ignoring", pkg)
                break
        else:
            packages_to_process.append(pkg)
    return packages_to_process


def run_conda_install(
    prefix: Path,
    specs: Iterable[MatchSpec],
    dry_run: bool = False,
    quiet: bool = False,
    verbosity: int = 0,
    force_reinstall: bool = False,
    yes: bool = False,
    json: bool = False,
) -> int:
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
    args: Iterable[str],
    upgrade: bool = False,
    dry_run: bool = False,
    quiet: bool = False,
    verbosity: int = 0,
    force_reinstall: bool = False,
    yes: bool = False,
    capture_output: bool = False,
    check: bool = True,
) -> CompletedProcess:
    if not args:
        return 0
    command = [
        get_env_python(prefix),
        "-mpip",
        "install",
        "--no-deps",
    ]
    if any(
        flag in args for flag in ("--platform", "--abi", "--implementation", "--python-version")
    ):
        command += ["--target", str(get_env_site_packages(prefix))]
    else:
        command += ["--prefix", str(prefix)]
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
    command.extend(args)

    logger.info("pip install command: %s", command)
    process = run(command, capture_output=capture_output or check, text=capture_output or check)
    if check and process.returncode:
        raise CondaError(
            f"Failed to run pip:\n"
            f"  command: {shlex.join(command)}\n"
            f"  exit code: {process.returncode}\n"
            f"  stderr:\n{process.stderr}\n"
            f"  stdout:\n{process.stdout}"
        )
    return process


def ensure_externally_managed(prefix: os.PathLike = None) -> Path:
    """
    conda-pypi places its own EXTERNALLY-MANAGED file when it is installed in an environment.
    We also need to place it in _new_ environments created by conda. We do this by implementing
    some extra plugin hooks.
    """
    target_path = next(get_externally_managed_path(prefix))
    if target_path.exists():
        return target_path
    logger.info("Placing EXTERNALLY-MANAGED in %s", target_path.parent)
    resource = importlib_files("conda_pypi") / "data" / "EXTERNALLY-MANAGED"
    target_path.write_text(resource.read_text())
    return target_path


def ensure_target_env_has_externally_managed(command: str):
    """
    post-command hook to ensure that the target env has the EXTERNALLY-MANAGED file
    even when it is created by conda, not 'conda-pypi'.
    """
    if os.environ.get("CONDA_BUILD_STATE") == "BUILD":
        return
    base_prefix = Path(context.conda_prefix)
    target_prefix = Path(context.target_prefix)
    if base_prefix == target_prefix:
        return
    # ensure conda-pypi was explicitly installed in base env (and not as a dependency)
    requested_specs_map = History(base_prefix).get_requested_specs_map()
    if requested_specs_map and "conda-pypi" not in requested_specs_map:
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


def pypi_lines_for_explicit_lockfile(
    prefix: Path | str, checksum: Literal["md5", "sha256"] | None = None
) -> list[str]:
    PrefixData._cache_.clear()
    pd = PrefixData(str(prefix), pip_interop_enabled=True)
    pd.load()
    lines = []
    python_record = list(pd.query("python"))
    assert len(python_record) == 1
    python_record = python_record[0]
    python_details = {"version": ".".join(python_record.version.split(".")[:3])}
    if "pypy" in python_record.build:
        python_details["implementation"] = "pp"
    else:
        python_details["implementation"] = "cp"
    for record in pd.iter_records():
        if record.package_type != PackageType.VIRTUAL_PYTHON_WHEEL:
            continue
        ignore = False
        wheel = {}
        hashed_record = ""
        for path in record.files:
            path = Path(context.target_prefix, path)
            if "__editable__" in path.stem:
                ignore = True
                break
            if path.name == "direct_url.json" and path.parent.suffix == ".dist-info":
                data = json.loads(path.read_text())
                if data.get("dir_info", {}).get("editable"):
                    ignore = True
                    break
            if checksum and path.name == "RECORD" and path.parent.suffix == ".dist-info":
                hashed_record = compute_record_sum(path, checksum)
            if path.name == "WHEEL" and path.parent.suffix == ".dist-info":
                for line in path.read_text().splitlines():
                    line = line.strip()
                    if ":" not in line:
                        continue
                    key, value = line.split(":", 1)
                    if key == "Tag":
                        wheel.setdefault(key, []).append(value.strip())
                    else:
                        wheel[key] = value.strip()
        if ignore:
            continue
        if record.url:
            lines.append(f"# pypi: {record.url}")
        else:
            seen = {"abi": set(), "platform": set()}
            lines.append(f"# pypi: {record.name}=={record.version}")
            lines[-1] += f" --python-version {python_details['version']}"
            lines[-1] += f" --implementation {python_details['implementation']}"
            if wheel and (wheel_tag := wheel.get("Tag")):
                for tag in wheel_tag:
                    _, abi_tag, platform_tag = tag.split("-", 2)
                    if abi_tag != "none" and abi_tag not in seen["abi"]:
                        lines[-1] += f" --abi {abi_tag}"
                        seen["abi"].add(abi_tag)
                    if platform_tag != "any" and platform_tag not in seen["platform"]:
                        lines[-1] += f" --platform {platform_tag}"
                        seen["platform"].add(platform_tag)
            # Here we could try to run a --dry-run --report some.json to get the resolved URL
            # but it's not guaranteed we get the exact same source so for now we defer to install
            # time
        if checksum and hashed_record:
            lines[-1] += f" -- --record-checksum={checksum}:{hashed_record}"

    return lines


def dry_run_pip_json(args: Iterable[str], force_reinstall: bool = False) -> dict[str, Any]:
    # pip can output to stdout via `--report -` (dash), but this
    # creates issues on Windows due to undecodable characters on some
    # project descriptions (e.g. charset-normalizer, amusingly), which
    # makes pip crash internally. Probably a bug on their end.
    # So we use a temporary file instead to work with bytes.
    json_output = NamedTemporaryFile(suffix=".json", delete=False)
    json_output.close()  # Prevent access errors on Windows

    cmd = [
        sys.executable,
        "-mpip",
        "install",
        "--dry-run",
        "--ignore-installed",
        *(("--force-reinstall",) if force_reinstall else ()),
        "--report",
        json_output.name,
        "--target",
        json_output.name + ".dir",
        *args,
    ]
    process = run(cmd, capture_output=True, text=True)
    if process.returncode != 0:
        raise CondaError(
            f"Failed to dry-run pip:\n"
            f"  command: {shlex.join(cmd)}\n"
            f"  exit code: {process.returncode}\n"
            f"  stderr:\n{process.stderr}\n"
            f"  stdout:\n{process.stdout}"
        )

    with open(json_output.name, "rb") as f:
        # We need binary mode because the JSON output might
        # contain weird unicode stuff (as part of the project
        # description or README).
        report = json.loads(f.read())
    os.unlink(json_output.name)
    return report


def compute_record_sum(record_path, algo):
    record = Path(record_path).read_text()
    lines = []
    for line in record.splitlines():
        path, *_ = line.split(",")
        path = Path(path)
        if path.parts[0].endswith(".dist-info") and path.name not in ("METADATA", "WHEEL"):
            # we only want to check the metadata and wheel parts of dist-info; everything else
            # is not deterministic or useful
            continue
        if path.parts[0] == ".." and ("bin" in path.parts or "lib" in path.parts):
            # entry points are autogenerated and can have different hashes/size depending on prefix
            path, *_ = line.split(",")
            line = f"{path},,"
        lines.append(line)
    with NamedTemporaryFile("w", delete=False) as tmp:
        tmp.write("\n".join(lines))

    try:
        return compute_sum(tmp.name, algo)
    finally:
        os.unlink(tmp.name)
