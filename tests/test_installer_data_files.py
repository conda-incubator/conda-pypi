"""
Tests for installer data file handling.

Tests that data files in wheels are properly installed.
"""

from pathlib import Path

import pytest
from conda.testing.fixtures import TmpEnvFixture
from conda.common.path import get_python_short_path
from conda.base.context import context

from conda_pypi import installer
from conda_pypi.build import build_pypa


@pytest.fixture(scope="session")
def test_package_wheel_path(tmp_path_factory):
    """Build a wheel from the test package with data files."""
    package_path = Path(__file__).parent / "packages" / "has-data-files"
    wheel_output = tmp_path_factory.mktemp("wheels")
    prefix = Path(context.default_prefix)

    return build_pypa(
        package_path,
        wheel_output,
        prefix=prefix,
        distribution="wheel",
    )


@pytest.mark.skip(reason="Test has CI-only failures that need investigation")
def test_install_installer_data_files_present(
    tmp_env: TmpEnvFixture,
    test_package_wheel_path: Path,
    tmp_path: Path,
):
    """Test that data files from wheels are installed in build_path."""
    build_path = tmp_path / "build"
    build_path.mkdir()

    with tmp_env("python=3.12", "pip") as prefix:
        python_executable = Path(prefix, get_python_short_path()) / "python"

        installer.install_installer(
            str(python_executable),
            test_package_wheel_path,
            build_path,
        )

        # Data files should be installed in build_path/share/ (data scheme)
        data_file = build_path / "share" / "test-package-with-data" / "data" / "test.txt"

        assert data_file.exists(), f"Data file not found at {data_file}"
