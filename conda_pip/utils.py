from __future__ import annotations

import os
import sys
import sysconfig
from logging import getLogger
from pathlib import Path
from subprocess import check_output
from typing import Iterator

from conda.base.context import context, locate_prefix_by_name
from conda.models.match_spec import MatchSpec


logger = getLogger(f"conda.{__name__}")


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
    return Path(
        check_output(
            [
                get_env_python(prefix),
                "-c",
                "import sysconfig; print(sysconfig.get_paths()['stdlib'])",
            ],
            text=True,
        ).strip()
    )


def get_externally_managed_path(prefix: os.PathLike = None) -> Iterator[Path]:
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

def pypi_spec_variants(spec_str: str) -> Iterator[str]:
    yield spec_str
    spec = MatchSpec(spec_str)
    for name_variant in (
        spec.name.replace("-", "_"),
        spec.name.replace("_", "-"),
    ):
        yield str(MatchSpec(spec, name=name_variant))