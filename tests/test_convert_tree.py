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
from conda_pypi.exceptions import CondaPypiError

import pytest

REPO = Path(__file__).parents[1] / "synthetic_repo"


def test_multiple(tmp_env: TmpEnvFixture, tmp_path: Path, monkeypatch: MockerFixture):
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
        converter = ConvertTree(prefix, repo=REPO, override_channels=True, finder=finder)
        changes = converter.convert_tree([TARGET_DEP])

        assert len(changes[0]) == 0
        assert len(changes[1]) == 1
        assert changes[1][0].name == "demo-package"


def test_package_without_wheel_should_fail_early(
    tmp_env: TmpEnvFixture, tmp_path: Path, monkeypatch
):
    """
    Test that when a package has no wheel available, the convert_tree method
    raises CondaPypiError with a meaningful message rather than looping for max_attempts.

    This verifies the fix for issue #121.
    """
    CONDA_PKGS_DIRS = tmp_path / "conda-pkgs"
    CONDA_PKGS_DIRS.mkdir()

    REPO.mkdir(parents=True, exist_ok=True)

    # "ach" is mentioned in the issue as an example package that only has source distributions
    TARGET_PKG = MatchSpec("ach")  # type: ignore

    # Defeat package cache for ConvertTree
    monkeypatch.setitem(os.environ, "CONDA_PKGS_DIRS", str(CONDA_PKGS_DIRS))

    with tmp_env("python=3.12", "pip") as prefix:
        converter = ConvertTree(prefix, repo=REPO, override_channels=True)

        # Should raise CondaPypiError immediately instead of looping
        with pytest.raises(CondaPypiError) as exc_info:
            converter.convert_tree([TARGET_PKG], max_attempts=5)

        # Verify we get a meaningful error message
        error_msg = str(exc_info.value).lower()
        assert "wheel" in error_msg
