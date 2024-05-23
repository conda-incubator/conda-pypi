from __future__ import annotations

import shlex
import sys
from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING

from conda.base.context import context
from conda.common.io import Spinner

from ..main import run_pip_install, dry_run_pip_json, compute_record_sum
from ..utils import get_env_site_packages

if TYPE_CHECKING:
    from typing import Iterable

log = getLogger(f"conda.{__name__}")


def _prepare_pypi_transaction(pypi_lines) -> dict[str, dict[str, str]]:
    pkgs = {}
    for args in pypi_lines:
        args = shlex.split(args)
        record_hash = None
        if "--" in args:
            double_dash_idx = args.index("--")
            if double_dash_idx >= 0:
                args, extra_args = args[:double_dash_idx], args[double_dash_idx:]
                if (
                    "--checksum" in extra_args
                    and (hash_idx := extra_args.index("--checksum")) > 0
                    and extra_args[hash_idx + 1].startswith(("md5:", "sha256:"))
                ):
                    record_hash = extra_args[hash_idx + 1]
                else:
                    for arg in extra_args:
                        if arg.startswith("--checksum="):
                            record_hash = arg.split("=", 1)[1]
        report = dry_run_pip_json(["--no-deps", *args])
        pkg_name = report["install"][0]["metadata"]["name"]
        version = report["install"][0]["metadata"]["version"]
        pkgs[(pkg_name, version)] = {"url": report["install"][0]["download_info"]["url"]}
        if record_hash:
            pkgs[(pkg_name, version)]["hash"] = record_hash
    return pkgs


def post_command(command: str) -> int:
    if command not in ("install", "create"):
        return 0

    pypi_lines = pypi_lines_from_sys_argv()
    if not pypi_lines:
        return 0

    with Spinner("\nPreparing PyPI transaction", enabled=not context.quiet, json=context.json):
        pkgs = _prepare_pypi_transaction(pypi_lines)

    with Spinner("Executing PyPI transaction", enabled=not context.quiet, json=context.json):
        run_pip_install(
            context.target_prefix,
            args=[pkg["url"] for pkg in pkgs.values()],
            dry_run=context.dry_run,
            quiet=context.quiet,
            verbosity=context.verbosity,
            force_reinstall=context.force_reinstall,
            yes=context.always_yes,
            check=True,
        )

    if any(pkg.get("hash") for pkg in pkgs.values()):
        with Spinner("Verifying PyPI transaction", enabled=not context.quiet, json=context.json):
            site_packages = get_env_site_packages(context.target_prefix)
            for dist_info in site_packages.glob("*.dist-info"):
                if not dist_info.is_dir():
                    continue
                name, version = dist_info.stem.split("-")
                expected_hash = pkgs.get((name, version), {}).get("hash")
                if expected_hash:
                    algo, expected_hash = expected_hash.split(":")
                    if (dist_info / "RECORD").is_file():
                        found_hash = compute_record_sum(dist_info / "RECORD", algo)
                        if expected_hash != found_hash:
                            log.warning(
                                "%s checksum for %s==%s didn't match! Expected=%s, found=%s",
                                algo,
                                name,
                                version,
                                expected_hash,
                                found_hash,
                            )

    return 0


def pypi_lines_from_sys_argv(argv: Iterable[str] | None = None) -> list[str]:
    argv = argv or sys.argv
    if "--file" not in argv:
        return []
    pypi_lines = []
    pypi_prefix = "# pypi: "
    pypi_prefix_len = len(pypi_prefix)
    for i, arg in enumerate(argv):
        if arg == "--file":
            pypi_lines += [
                line[pypi_prefix_len:]
                for line in Path(argv[i + 1]).read_text().splitlines()
                if line.strip().startswith(pypi_prefix)
            ]
    return pypi_lines
