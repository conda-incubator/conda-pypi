from __future__ import annotations

import json
import os
import shlex
import sys
from csv import reader as csv_reader
from email.parser import HeaderParser
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
from conda.common.pkg_formats.python import PythonDistribution
from conda.core.prefix_data import PrefixData
from conda.gateways.disk.read import compute_sum
from conda.models.enums import PackageType
from conda.models.records import PackageRecord
from conda.history import History
from conda.cli.python_api import run_command
from conda.exceptions import CondaError, CondaSystemExit
from conda.models.match_spec import MatchSpec
from packaging.tags import parse_tag

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
    for record in pd.iter_records():
        if record.package_type != PackageType.VIRTUAL_PYTHON_WHEEL:
            continue
        pypi_dist = PyPIDistribution.from_conda_record(
            record, python_record, prefix, checksum=checksum
        )
        if pypi_dist.editable:
            continue
        lines.append(pypi_dist.to_lockfile_line())
    return lines


def dry_run_pip_json(args: Iterable[str], force_reinstall: bool = False) -> dict[str, Any]:
    # pip can output to stdout via `--report -` (dash), but this
    # creates issues on Windows due to undecodable characters on some
    # project descriptions (e.g. charset-normalizer, amusingly), which
    # makes pip crash internally. Probably a bug on their end.
    # So we use a temporary file instead to work with bytes.
    json_output = NamedTemporaryFile(suffix=".json", delete=False)
    json_output.close()  # Prevent access errors on Windows

    try:
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
            json_output.name + ".dir",  # This won't be created
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
            return json.loads(f.read())
    finally:
        os.unlink(json_output.name)


class PyPIDistribution:
    _line_prefix = "# pypi: "

    def __init__(
        self,
        name: str,
        version: str,
        python_version: str | None = None,
        python_implementation: str | None = None,
        python_abi_tags: Iterable[str] = (),
        python_platform_tags: Iterable[str] = (),
        files_hash: str | None = None,
        editable: bool = False,
    ):
        self.name = name
        self.version = version
        self.python_version = python_version
        self.python_implementation = python_implementation
        self.python_abi_tags = python_abi_tags or ()
        self.python_platform_tags = python_platform_tags or ()
        self.files_hash = files_hash
        self.editable = editable
        self.url = None  # currently no way to know

    @classmethod
    def from_conda_record(
        cls,
        record: PackageRecord,
        python_record: PackageRecord,
        prefix: str | Path,
        checksum: Literal["md5", "sha256"] | None = None,
    ) -> PyPIDistribution:
        # Locate anchor file
        sitepackages = get_env_site_packages(prefix)
        if record.fn.endswith(".dist-info"):
            anchor = sitepackages / record.fn / "METADATA"
        elif record.fn.endswith(".egg-info"):
            anchor = sitepackages / record.fn
            if anchor.is_dir():
                anchor = anchor / "PKG-INFO"
        else:
            raise ValueError("Unrecognized anchor file for Python metadata")

        # Estimate python implementation out of build strings
        python_version = ".".join(python_record.version.split(".")[:3])
        if "pypy" in python_record.build:
            python_impl = "pp"
        elif "cpython" in python_record.build:
            python_impl = "cp"
        else:
            python_impl = None

        # Find the hash for the RECORD file
        python_dist = PythonDistribution.init(prefix, str(anchor), python_record.version)
        if checksum:
            manifest = python_dist.manifest_full_path
            hashed_files = f"{checksum}:{compute_record_sum(manifest, checksum)}"
        else:
            hashed_files = None

        # Scan files for editable markers and wheel metadata
        files = python_dist.get_paths()
        editable = cls._is_record_editable(files)
        wheel_file = next((path for path, *_ in files if path.endswith(".dist-info/WHEEL")), None)
        if wheel_file:
            wheel_details = cls._parse_wheel_file(Path(prefix, wheel_file))
            abi_tags, platform_tags = cls._tags_from_wheel(wheel_details)
        else:
            abi_tags, platform_tags = (), ()

        return cls(
            name=record.name,
            version=record.version,
            python_version=python_version,
            python_implementation=python_impl,
            files_hash=hashed_files,
            python_abi_tags=abi_tags,
            python_platform_tags=platform_tags,
            editable=editable,
        )

    def to_lockfile_line(self) -> list[str]:
        if self.url:
            return f"{self._line_prefix}{self.url}"

        line = (
            f"{self._line_prefix}{self.name}=={self.version}"
            f" --python-version {self.python_version}"
            f" --implementation {self.python_implementation}"
        )
        for abi in self.python_abi_tags:
            line += f" --abi {abi}"
        for platform in self.python_platform_tags:
            line += f" --platform {platform}"
        if self.files_hash:
            line += f" -- --record-checksum={self.files_hash}"

        # Here we could try to run a pip --dry-run --report some.json to get the resolved URL
        # but it's not guaranteed we get the exact same source so for now we defer to install
        # time

        return line

    @staticmethod
    def _parse_wheel_file(path) -> dict[str, list[str]]:
        path = Path(path)
        if not path.is_file():
            return {}
        with open(path) as f:
            parsed = HeaderParser().parse(f)
        data = {}
        for key, value in parsed.items():
            data.setdefault(key, []).append(value)
        return data

    @staticmethod
    def _tags_from_wheel(data: dict[str, Any]) -> tuple[tuple[str], tuple[str]]:
        abi_tags = set()
        platform_tags = set()
        for tag_str in data.get("Tag", ()):
            for tag in parse_tag(tag_str):
                if tag.abi != "none":
                    abi_tags.add(tag.abi)
                if tag.platform != "any":
                    platform_tags.add(tag.platform)
        return tuple(abi_tags), tuple(platform_tags)

    @staticmethod
    def _is_record_editable(files: tuple[str, str, int]) -> bool:
        for path, *_ in files:
            path = Path(path)
            if "__editable__" in path.stem:
                return True
            if path.name == "direct_url.json" and path.parent.suffix == ".dist-info":
                if path.is_file():
                    data = json.loads(path.read_text())
                    if data.get("dir_info", {}).get("editable"):
                        return True
        return False


def compute_record_sum(manifest: str, algo: str = "sha256") -> str:
    """
    Given a RECORD file, compute a hash out of a subset of its sorted contents.

    We skip *.dist-info files other than METADATA and WHEEL.
    For non site-packages files, we only keep the path for those than fall in bin, lib and Scripts
    because their hash and size might change with path relocation.

    The list of tuples (path, hash, size) is then sorted and written as JSON with no spaces or
    indentation. This output is what gets hashed.
    """
    manifest = Path(manifest)
    if not manifest.is_file():
        return
    contents = []
    with open(manifest) as f:
        reader = csv_reader(f, delimiter=",", quotechar='"')
        for row in reader:
            path, hash_, size = row
            path = Path(path)
            if size:
                size = int(size)
            if path.parts[0].endswith(".dist-info") and path.name not in ("METADATA", "WHEEL"):
                # we only want to check the metadata and wheel parts of dist-info; everything else
                # is not deterministic or useful
                continue
            if path.parts[0] == ".." and any(
                part in path.parts for part in ("bin", "lib", "Scripts")
            ):
                # entry points are autogenerated and can have different hashes/size
                # depending on prefix
                hash_, size = "", 0
            contents.append((str(path), hash_, size))

    try:
        with NamedTemporaryFile("w", delete=False) as tmp:
            tmp.write(json.dumps(contents, indent=0, separators=(",", ":")))
        return compute_sum(tmp.name, algo)
    finally:
        os.unlink(tmp.name)
