"""
Essential tests for conda_pypi.utils EXTERNALLY-MANAGED functionality.
"""

import os
import sys
from pathlib import Path

from conda_pypi.utils import (
    get_externally_managed_paths,
    ensure_externally_managed,
    get_env_stdlib,
)


def test_externally_managed_workflow(tmp_path):
    """Test complete workflow: paths, creation, content, idempotency."""
    if os.name == "nt":
        lib_dir = tmp_path / "Lib"
        lib_dir.mkdir()
    else:
        python_dir = tmp_path / "lib" / "python3.11"
        python_dir.mkdir(parents=True)

    paths = get_externally_managed_paths(tmp_path)
    assert len(paths) >= 1

    ensure_externally_managed(tmp_path)

    em_files = list(tmp_path.rglob("EXTERNALLY-MANAGED"))
    assert len(em_files) >= 1

    content = em_files[0].read_text()
    assert content.startswith("[externally-managed]")
    assert "conda pypi" in content  # Should contain the standard message

    # Test idempotency - calling again should not change the content
    ensure_externally_managed(tmp_path)
    assert em_files[0].read_text() == content


def test_get_env_stdlib_current_environment():
    """Test get_env_stdlib works with current Python environment."""
    result = get_env_stdlib(sys.prefix)

    assert isinstance(result, Path)
    assert result.exists()
    assert result.is_dir()
    assert "site-packages" not in str(result)

    has_stdlib_files = (
        (result / "os.py").exists()
        or (result / "lib-dynload").exists()
        or (result / "collections").exists()
    )
    assert has_stdlib_files
