"""
Test converting a dependency tree to conda.
"""

import os
from pathlib import Path

from conda.models.match_spec import MatchSpec
from conda.testing.fixtures import TmpEnvFixture
from pytest_mock import MockerFixture

from conda_pypi.convert_tree import ConvertTree
from conda_pypi.downloader import get_package_finder


REPO = Path(__file__).parents[1] / "synthetic_repo"


def test_multiple(
    tmp_env: TmpEnvFixture,
    tmp_path: Path, 
    monkeypatch: MockerFixture
):
    """
    Install multiple only-available-from-pypi dependencies into an environment.
    """
    CONDA_PKGS_DIRS = tmp_path / "conda-pkgs"
    CONDA_PKGS_DIRS.mkdir()

    WHEEL_DIR = tmp_path / "wheels"
    WHEEL_DIR.mkdir(exist_ok=True)

    REPO.mkdir(parents=True, exist_ok=True)

    TARGET_DEP = MatchSpec("twine==5.1.1")  # type: ignore

    # Defeat package cache for ConvertTree
    monkeypatch.setitem(os.environ, "CONDA_PKGS_DIRS", str(CONDA_PKGS_DIRS))

    with tmp_env("python=3.12", "pip") as prefix:
        converter = ConvertTree(prefix, repo=REPO, override_channels=True)
        converter.convert_tree([TARGET_DEP])


def test_convert_local_pypi_package(
    tmp_env: TmpEnvFixture,
    tmp_path: Path, 
    monkeypatch: MockerFixture,
    pypi_local_index: str,
):
    """
    Convert a local pypi package
    """
    CONDA_PKGS_DIRS = tmp_path / "conda-pkgs"
    CONDA_PKGS_DIRS.mkdir()

    WHEEL_DIR = tmp_path / "wheels"
    WHEEL_DIR.mkdir(exist_ok=True)

    REPO.mkdir(parents=True, exist_ok=True)

    TARGET_DEP = MatchSpec("demo-package")  # type: ignore

    # Defeat package cache for ConvertTree
    monkeypatch.setitem(os.environ, "CONDA_PKGS_DIRS", str(CONDA_PKGS_DIRS))

    with tmp_env("python=3.12", "pip") as prefix:
        finder = get_package_finder(prefix, (pypi_local_index,))
        converter = ConvertTree(
            prefix,
            repo=REPO,
            override_channels=True,
            finder = finder
        )
        changes = converter.convert_tree([TARGET_DEP])

        assert len(changes[0]) == 0
        assert len(changes[1]) == 1
        assert changes[1][0].name == "demo-package" 
