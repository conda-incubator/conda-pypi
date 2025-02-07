"""
Check dependencies in a prefix, either by using Conda's functionality or
Python's in a subprocess.
"""

import importlib.resources
import json
import subprocess
import sys
from pathlib import Path
from typing import Iterable

from conda.cli.main import main_subshell

from . import paths
from .translate import requires_to_conda


def check_dependencies(requirements: Iterable[str], prefix: Path):
    python_executable = str(paths.get_python_executable(prefix))
    dependency_getter = importlib.resources.read_text(
        "conda_pupa", "dependencies_subprocess.py"
    )
    try:
        result = subprocess.run(
            [
                python_executable,
                "-I",
                "-",
                "-r",
                json.dumps(sorted(requirements)),
            ],
            encoding="utf-8",
            input=dependency_getter,
            capture_output=True,
            check=True,
        )
        missing = json.loads(result.stdout)
    except subprocess.SubprocessError as e:
        # XXX what exception to raise?
        print(e, file=sys.stderr)
        return []

    return missing


def ensure_requirements(requirements: list[str], prefix: Path):
    if requirements:
        conda_requirements, _ = requires_to_conda(requirements)
        # -y may be appropriate during tests only
        main_subshell("install", "--prefix", str(prefix), "-y", *conda_requirements)
