from __future__ import annotations

import shlex
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from conda.base.context import context
from conda.common.io import Spinner

from ..main import run_pip_install, pip_install_download_info

if TYPE_CHECKING:
    from typing import Iterable


def post_command(command: str) -> int:
    if command not in ("install", "create"):
        return 0

    installed = []
    pypi_lines = pypi_lines_from_sys_argv()
    if not pypi_lines:
        return 0

    with Spinner(
        f"Installing PyPI packages ({len(pypi_lines)})",
        enabled=not context.quiet,
        json=context.json,
    ):
        for args in pypi_lines:
            args = shlex.split(args)
            dl_info = pip_install_download_info(args)
            run_pip_install(
                context.target_prefix,
                args=[dl_info["url"]],
                dry_run=context.dry_run,
                quiet=context.quiet,
                verbosity=context.verbosity,
                force_reinstall=context.force_reinstall,
                yes=context.always_yes,
                check=True,
            )
            installed.append(args[0])
    print("Successfully installed PyPI packages:", *installed)
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
