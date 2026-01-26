"""Tests for conda_pypi.python_paths module."""

import sys
from pathlib import Path

import pytest

from conda_pypi.python_paths import get_externally_managed_path, get_externally_managed_paths


@pytest.mark.skipif(sys.platform == "win32", reason="Unix only")
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


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_get_externally_managed_path_with_version_windows():
    prefix = Path("C:/test_env")

    expected = prefix / "Lib" / "EXTERNALLY-MANAGED"
    assert get_externally_managed_path(prefix, "3.12") == expected
    assert get_externally_managed_path(prefix, "3.11") == expected


@pytest.mark.skipif(sys.platform == "win32", reason="Unix only")
def test_get_externally_managed_path_without_version_unix():
    prefix = Path("/tmp/test_env")
    current_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    expected = prefix / "lib" / f"python{current_version}" / "EXTERNALLY-MANAGED"

    assert get_externally_managed_path(prefix) == expected


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_get_externally_managed_path_without_version_windows():
    prefix = Path("C:/test_env")
    expected = prefix / "Lib" / "EXTERNALLY-MANAGED"

    assert get_externally_managed_path(prefix) == expected


@pytest.mark.skipif(sys.platform == "win32", reason="Unix only")
def test_get_externally_managed_path_default_prefix_unix():
    current_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    expected = Path(sys.prefix) / "lib" / f"python{current_version}" / "EXTERNALLY-MANAGED"

    assert get_externally_managed_path() == expected


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_get_externally_managed_path_default_prefix_windows():
    expected = Path(sys.prefix) / "Lib" / "EXTERNALLY-MANAGED"

    assert get_externally_managed_path() == expected


@pytest.mark.skipif(sys.platform == "win32", reason="Unix only")
def test_externally_managed_python_upgrade_unix(tmp_path):
    """Test that EXTERNALLY-MANAGED is created correctly for different Python versions on Unix."""
    from conda_pypi.python_paths import ensure_externally_managed

    prefix = tmp_path / "env"

    # Create EXTERNALLY-MANAGED for Python 3.11
    ensure_externally_managed(prefix, python_version="3.11")
    py311_managed = prefix / "lib" / "python3.11" / "EXTERNALLY-MANAGED"
    assert py311_managed.exists()
    assert "[externally-managed]" in py311_managed.read_text()

    # Upgrade to Python 3.12 (cleanup old, create new)
    for path in get_externally_managed_paths(prefix):
        if path.exists():
            path.unlink()

    ensure_externally_managed(prefix, python_version="3.12")
    py312_managed = prefix / "lib" / "python3.12" / "EXTERNALLY-MANAGED"

    assert not py311_managed.exists()
    assert py312_managed.exists()
    assert "conda pypi" in py312_managed.read_text().lower()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_externally_managed_python_upgrade_windows(tmp_path):
    """Test that EXTERNALLY-MANAGED is created correctly on Windows (no version-specific path)."""
    from conda_pypi.python_paths import ensure_externally_managed

    prefix = tmp_path / "env"

    # On Windows, version doesn't matter - always in Lib/
    ensure_externally_managed(prefix, python_version="3.11")
    managed = prefix / "Lib" / "EXTERNALLY-MANAGED"
    assert managed.exists()
    assert "[externally-managed]" in managed.read_text()

    # "Upgrade" to Python 3.12 - same file location on Windows
    for path in get_externally_managed_paths(prefix):
        if path.exists():
            path.unlink()

    ensure_externally_managed(prefix, python_version="3.12")

    # Same path is used regardless of version
    assert managed.exists()
    assert "conda pypi" in managed.read_text().lower()
