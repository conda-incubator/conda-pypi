"""Tests for conda_pypi.python_paths module."""

import sys
from pathlib import Path

import pytest

from conda_pypi.python_paths import get_externally_managed_path


@pytest.mark.skipif(sys.platform == "win32", reason="Unix-specific test")
def test_get_externally_managed_path_with_version_unix():
    """Test that get_externally_managed_path constructs correct paths on Unix."""
    prefix = Path("/tmp/test_env")

    assert (
        get_externally_managed_path(prefix, "3.12")
        == prefix / "lib" / "python3.12" / "EXTERNALLY-MANAGED"
    )
    assert (
        get_externally_managed_path(prefix, "3.11")
        == prefix / "lib" / "python3.11" / "EXTERNALLY-MANAGED"
    )


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test")
def test_get_externally_managed_path_with_version_windows():
    prefix = Path("C:/test_env")

    expected = prefix / "Lib" / "EXTERNALLY-MANAGED"
    assert get_externally_managed_path(prefix, "3.12") == expected
    assert get_externally_managed_path(prefix, "3.11") == expected


@pytest.mark.skipif(sys.platform == "win32", reason="Unix-specific test")
def test_get_externally_managed_path_without_version_unix():
    prefix = Path("/tmp/test_env")
    current_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    expected = prefix / "lib" / f"python{current_version}" / "EXTERNALLY-MANAGED"

    assert get_externally_managed_path(prefix) == expected


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test")
def test_get_externally_managed_path_without_version_windows():
    prefix = Path("C:/test_env")
    expected = prefix / "Lib" / "EXTERNALLY-MANAGED"

    assert get_externally_managed_path(prefix) == expected


@pytest.mark.skipif(sys.platform == "win32", reason="Unix-specific test")
def test_get_externally_managed_path_default_prefix_unix():
    current_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    expected = Path(sys.prefix) / "lib" / f"python{current_version}" / "EXTERNALLY-MANAGED"

    assert get_externally_managed_path() == expected


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test")
def test_get_externally_managed_path_default_prefix_windows():
    expected = Path(sys.prefix) / "Lib" / "EXTERNALLY-MANAGED"

    assert get_externally_managed_path() == expected
