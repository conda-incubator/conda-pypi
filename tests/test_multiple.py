"""
Test converting a dependency tree to conda.
"""

import json
import os
import pathlib
import subprocess

from conda.models.match_spec import MatchSpec

from conda_pupa.convert_tree import ConvertTree

REPO = pathlib.Path(__file__).parents[1] / "synthetic_repo"


def list_envs():
    output = subprocess.run(
        f"{os.environ['CONDA_EXE']} info --envs --json".split(),
        capture_output=True,
        check=True,
    )
    env_info = json.loads(output.stdout)
    return env_info


def create_test_env(prefix):
    """
    Create named environment at prefix.
    """
    subprocess.run(
        [os.environ["CONDA_EXE"], "create", "-p", prefix, "-y", "python 3.12"],
        check=True,
        encoding="utf-8",
    )


def test_multiple(tmp_path, monkeypatch):
    """
    Install multiple only-available-from-pypi dependencies into an environment.
    """
    TARGET_ENV_PATH = tmp_path / "pupa-target"
    TARGET_ENV_PATH.mkdir()

    CONDA_PKGS_DIRS = tmp_path / "conda-pkgs"
    CONDA_PKGS_DIRS.mkdir()

    create_test_env(TARGET_ENV_PATH)

    WHEEL_DIR = tmp_path / "wheels"
    WHEEL_DIR.mkdir(exist_ok=True)

    REPO.mkdir(parents=True, exist_ok=True)

    TARGET_DEP = MatchSpec("twine==5.1.1")  # type: ignore

    # Defeat package cache for ConvertTree
    monkeypatch.setitem(os.environ, "CONDA_PKGS_DIRS", str(CONDA_PKGS_DIRS))

    converter = ConvertTree(TARGET_ENV_PATH, repo=REPO, override_channels=True)
    converter.convert_tree([TARGET_DEP])
