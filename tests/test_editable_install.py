from __future__ import annotations

import os
import sys
from pathlib import Path
from subprocess import run

from conda.core.prefix_data import PrefixData
from conda.testing import CondaCLIFixture, TmpEnvFixture

from conda_pypi.utils import get_env_python, get_env_site_packages


def test_local_editable_install_basic(
    tmp_path: Path, tmp_env: TmpEnvFixture, conda_cli: CondaCLIFixture
):
    """Test basic local editable install functionality."""
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"

    # Create a test package
    test_pkg_dir = tmp_path / "test_editable_pkg"
    test_pkg_dir.mkdir()

    # Create pyproject.toml
    (test_pkg_dir / "pyproject.toml").write_text("""
[build-system]
requires = ["setuptools", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "test-editable-pkg"
version = "1.0.0"
description = "Test package for editable installs"
""")

    # Create package module
    pkg_module_dir = test_pkg_dir / "test_editable_pkg"
    pkg_module_dir.mkdir()
    (pkg_module_dir / "__init__.py").write_text("""
__version__ = "1.0.0"

def get_message():
    return "Hello from editable package!"
""")

    os.chdir(tmp_path)
    with tmp_env(f"python={python_version}", "pip") as prefix:
        # Install in editable mode
        out, err, rc = conda_cli(
            "pypi",
            "-p",
            prefix,
            "--yes",
            "install",
            "-e",
            str(test_pkg_dir),
        )
        print("Editable install output:")
        print(out)
        print(err, file=sys.stderr)
        assert rc == 0, "Editable install should succeed"

        # Verify package appears in conda list with editable version
        PrefixData._cache_.clear()
        pd = PrefixData(str(prefix), interoperability=True)
        installed_records = list(pd.query("test-editable-pkg"))
        assert len(installed_records) == 1, "Package should be installed"

        record = installed_records[0]
        assert "editable" in record.version, f"Version should indicate editable: {record.version}"

        # Verify package can be imported and works
        python_exe = get_env_python(prefix)
        result = run(
            [
                str(python_exe),
                "-c",
                "import test_editable_pkg; print(test_editable_pkg.get_message())",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Import failed: {result.stderr}"
        assert "Hello from editable package!" in result.stdout


def test_local_editable_install_live_development(
    tmp_path: Path, tmp_env: TmpEnvFixture, conda_cli: CondaCLIFixture
):
    """Test that local editable installs support live development (source changes are immediately visible)."""
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"

    # Create a test package
    test_pkg_dir = tmp_path / "live_test_pkg"
    test_pkg_dir.mkdir()

    # Create pyproject.toml
    (test_pkg_dir / "pyproject.toml").write_text("""
[build-system]
requires = ["setuptools", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "live-test-pkg"
version = "2.0.0"
description = "Test package for live development"
""")

    # Create package module with initial content
    pkg_module_dir = test_pkg_dir / "live_test_pkg"
    pkg_module_dir.mkdir()
    init_file = pkg_module_dir / "__init__.py"
    init_file.write_text("""
__version__ = "2.0.0"

def get_value():
    return "original value"

def get_number():
    return 42
""")

    os.chdir(tmp_path)
    with tmp_env(f"python={python_version}", "pip") as prefix:
        # Install in editable mode
        out, err, rc = conda_cli(
            "pypi",
            "-p",
            prefix,
            "--yes",
            "install",
            "-e",
            str(test_pkg_dir),
        )
        assert rc == 0, "Editable install should succeed"

        python_exe = get_env_python(prefix)

        # Test original functionality
        result = run(
            [str(python_exe), "-c", "import live_test_pkg; print(live_test_pkg.get_value())"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Initial import failed: {result.stderr}"
        assert "original value" in result.stdout

        # Modify the source code
        init_file.write_text("""
__version__ = "2.0.0"

def get_value():
    return "updated value"

def get_number():
    return 100

def new_function():
    return "brand new feature"
""")

        # Test that changes are immediately visible (no reinstall needed)
        result = run(
            [str(python_exe), "-c", "import live_test_pkg; print(live_test_pkg.get_value())"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Import after modification failed: {result.stderr}"
        assert "updated value" in result.stdout, "Source changes should be immediately visible"

        # Test new function works
        result = run(
            [str(python_exe), "-c", "import live_test_pkg; print(live_test_pkg.new_function())"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"New function import failed: {result.stderr}"
        assert (
            "brand new feature" in result.stdout
        ), "New functions should be immediately available"

        # Test updated number
        result = run(
            [str(python_exe), "-c", "import live_test_pkg; print(live_test_pkg.get_number())"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Updated function import failed: {result.stderr}"
        assert "100" in result.stdout, "Updated function values should be immediately visible"


def test_local_editable_install_conda_integration(
    tmp_path: Path, tmp_env: TmpEnvFixture, conda_cli: CondaCLIFixture
):
    """Test that editable installs integrate properly with conda package management."""
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"

    # Create a test package
    test_pkg_dir = tmp_path / "conda_integration_pkg"
    test_pkg_dir.mkdir()

    # Create pyproject.toml
    (test_pkg_dir / "pyproject.toml").write_text("""
[build-system]
requires = ["setuptools", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "conda-integration-pkg"
version = "3.0.0"
description = "Test package for conda integration"
""")

    # Create package module
    pkg_module_dir = test_pkg_dir / "conda_integration_pkg"
    pkg_module_dir.mkdir()
    (pkg_module_dir / "__init__.py").write_text("""
__version__ = "3.0.0"

def integration_test():
    return "conda integration works"
""")

    os.chdir(tmp_path)
    with tmp_env(f"python={python_version}", "pip") as prefix:
        # Install in editable mode
        out, err, rc = conda_cli(
            "pypi",
            "-p",
            prefix,
            "--yes",
            "install",
            "-e",
            str(test_pkg_dir),
        )
        assert rc == 0, "Editable install should succeed"

        # Verify package appears in conda list
        out, err, rc = conda_cli("list", "-p", prefix)
        assert rc == 0, "conda list should succeed"
        assert "conda-integration-pkg" in out, "Package should appear in conda list"
        assert "editable" in out, "Package should be marked as editable"

        # Verify package can be removed with conda remove
        out, err, rc = conda_cli("remove", "-p", prefix, "--yes", "conda-integration-pkg")
        assert rc == 0, "conda remove should succeed"

        # Verify package is no longer in conda list
        out, err, rc = conda_cli("list", "-p", prefix)
        assert rc == 0, "conda list should succeed after removal"
        assert "conda-integration-pkg" not in out, "Package should be removed from conda list"

        # Note: After conda remove, the .pth file is removed but the source code still exists
        # This is expected behavior - conda only manages the symlink, not the source


def test_local_editable_install_error_handling(
    tmp_path: Path, tmp_env: TmpEnvFixture, conda_cli: CondaCLIFixture
):
    """Test error handling for invalid packages in editable mode."""
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"

    os.chdir(tmp_path)
    with tmp_env(f"python={python_version}", "pip") as prefix:
        # Test with non-existent directory - should succeed with warning
        out, err, rc = conda_cli(
            "pypi",
            "-p",
            prefix,
            "--yes",
            "install",
            "-e",
            "./non_existent_dir",
        )
        # The CLI reports success even if no packages were processed
        # This matches the behavior of regular installs
        assert rc == 0, "CLI should succeed even with warnings"

        # Test with directory without Python project files - should succeed with warning
        empty_dir = tmp_path / "empty_dir"
        empty_dir.mkdir()

        out, err, rc = conda_cli(
            "pypi",
            "-p",
            prefix,
            "--yes",
            "install",
            "-e",
            str(empty_dir),
        )
        # Again, CLI reports success even if no packages were processed
        assert rc == 0, "CLI should succeed even with warnings"


def test_local_editable_install_pth_file_creation(
    tmp_path: Path, tmp_env: TmpEnvFixture, conda_cli: CondaCLIFixture
):
    """Test that .pth files are correctly created for editable installs."""
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"

    # Create a test package
    test_pkg_dir = tmp_path / "pth_test_pkg"
    test_pkg_dir.mkdir()

    # Create pyproject.toml
    (test_pkg_dir / "pyproject.toml").write_text("""
[build-system]
requires = ["setuptools", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "pth-test-pkg"
version = "4.0.0"
description = "Test package for .pth file verification"
""")

    # Create package module
    pkg_module_dir = test_pkg_dir / "pth_test_pkg"
    pkg_module_dir.mkdir()
    (pkg_module_dir / "__init__.py").write_text("""
__version__ = "4.0.0"
""")

    os.chdir(tmp_path)
    with tmp_env(f"python={python_version}", "pip") as prefix:
        # Install in editable mode
        out, err, rc = conda_cli(
            "pypi",
            "-p",
            prefix,
            "--yes",
            "install",
            "-e",
            str(test_pkg_dir),
        )
        assert rc == 0, "Editable install should succeed"

        # Verify .pth file was created
        site_packages = get_env_site_packages(prefix)
        pth_files = list(site_packages.glob("__pth_test_pkg__path__.pth"))
        assert len(pth_files) == 1, f"Should have exactly one .pth file, found {len(pth_files)}"

        # Verify .pth file points to correct source directory
        pth_file = pth_files[0]
        pth_content = pth_file.read_text().strip()
        assert (
            str(test_pkg_dir.resolve()) == pth_content
        ), f"pth file should point to {test_pkg_dir.resolve()}, but contains {pth_content}"

        # Verify dist-info directory was created
        dist_info_dirs = list(site_packages.glob("pth-test-pkg-*.dist-info"))
        assert (
            len(dist_info_dirs) == 1
        ), f"Should have exactly one dist-info directory, found {len(dist_info_dirs)}"

        # Verify dist-info contains expected files
        dist_info = dist_info_dirs[0]
        assert (dist_info / "METADATA").exists(), "METADATA file should exist"
        assert (dist_info / "INSTALLER").exists(), "INSTALLER file should exist"
        assert (dist_info / "top_level.txt").exists(), "top_level.txt file should exist"

        # Verify INSTALLER file contains "conda-pypi"
        installer_content = (dist_info / "INSTALLER").read_text().strip()
        assert (
            installer_content == "conda-pypi"
        ), f"INSTALLER should contain 'conda-pypi', but contains '{installer_content}'"


def test_local_editable_install_without_dependencies(
    tmp_path: Path, tmp_env: TmpEnvFixture, conda_cli: CondaCLIFixture
):
    """Test that editable installs currently don't handle dependencies (by design).

    Note: Our current editable install implementation creates a symlink-based
    conda package that doesn't resolve or install dependencies. This matches
    pip's --no-deps behavior. If dependencies are needed, they should be
    installed separately or the package should be installed with dependencies first.
    """
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"

    # Create a test package with dependencies
    test_pkg_dir = tmp_path / "no_deps_test_pkg"
    test_pkg_dir.mkdir()

    # Create pyproject.toml with dependencies
    (test_pkg_dir / "pyproject.toml").write_text("""
[build-system]
requires = ["setuptools", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "no-deps-test-pkg"
version = "5.0.0"
description = "Test package showing dependency handling"
dependencies = ["packaging"]
""")

    # Create package module that doesn't use dependencies
    pkg_module_dir = test_pkg_dir / "no_deps_test_pkg"
    pkg_module_dir.mkdir()
    (pkg_module_dir / "__init__.py").write_text("""
__version__ = "5.0.0"

def simple_function():
    return "No dependencies needed for this function"
""")

    os.chdir(tmp_path)
    with tmp_env(f"python={python_version}", "pip") as prefix:
        # Install packaging first (simulating manual dependency management)
        out, err, rc = conda_cli(
            "pypi",
            "-p",
            prefix,
            "--yes",
            "install",
            "packaging",
        )
        assert rc == 0, "Dependency install should succeed"

        # Install our package in editable mode
        out, err, rc = conda_cli(
            "pypi",
            "-p",
            prefix,
            "--yes",
            "install",
            "-e",
            str(test_pkg_dir),
        )
        assert rc == 0, "Editable install should succeed"

        # Verify our package can be imported
        python_exe = get_env_python(prefix)
        result = run(
            [
                str(python_exe),
                "-c",
                "import no_deps_test_pkg; print(no_deps_test_pkg.simple_function())",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Import failed: {result.stderr}"
        assert "No dependencies needed" in result.stdout

        # Verify both our package and the pre-installed dependency are in conda list
        out, err, rc = conda_cli("list", "-p", prefix)
        assert rc == 0, "conda list should succeed"
        assert "no-deps-test-pkg" in out, "Our package should appear in conda list"
        assert "packaging" in out, "Pre-installed dependency should appear in conda list"
