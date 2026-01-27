"""
QA tests for PyPI wheel installation and import verification.

These tests are designed to be run manually via the --qa-packages CLI option
or through the GitHub Actions workflow. They install arbitrary PyPI packages
and verify they can be imported successfully.

Usage:
    pytest -m qa --qa-packages requests --qa-packages numpy tests/test_qa_wheels.py -v
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from conda.common.path import get_python_short_path
from conda_pypi.python_paths import get_env_site_packages


def pytest_generate_tests(metafunc):
    """Dynamically parametrize tests based on --qa-packages CLI option"""
    if "package_name" in metafunc.fixturenames:
        packages = metafunc.config.getoption("--qa-packages")
        if packages:
            metafunc.parametrize("package_name", packages)
        else:
            # Skip this test if no packages are provided
            metafunc.parametrize("package_name", [], ids=lambda x: x)


def get_import_names_from_metadata(prefix: Path, package_name: str) -> list[str]:
    """
    Parse dist-info/top_level.txt to determine import names.

    Package names on PyPI may differ from import names (e.g., PyYAML -> yaml).
    Returns list of top-level module names from the package metadata.
    Falls back to [package_name] if metadata cannot be found.
    """
    site_packages = get_env_site_packages(prefix)

    # Normalize package name for searching (PyPI names can have various separators)
    # dist-info directories use normalized names with underscores and dashes
    normalized_name = package_name.lower().replace("-", "_")

    # Find dist-info directory matching package name
    # Try multiple patterns as package names can vary
    dist_info_patterns = [
        f"{normalized_name}-*.dist-info",
        f"{package_name.lower().replace('_', '-')}-*.dist-info",
        f"{package_name}-*.dist-info",
    ]

    dist_info_dir = None
    for pattern in dist_info_patterns:
        matches = list(site_packages.glob(pattern))
        if matches:
            # Use the first match (there should typically be only one)
            dist_info_dir = matches[0]
            break

    if not dist_info_dir:
        # Fallback: try the package name itself
        return [package_name.replace("-", "_")]

    # Read top_level.txt if it exists
    top_level_file = dist_info_dir / "top_level.txt"
    if top_level_file.exists():
        import_names = [
            line.strip() for line in top_level_file.read_text().splitlines() if line.strip()
        ]
        return import_names if import_names else [package_name.replace("-", "_")]

    # Fallback to normalized package name if top_level.txt doesn't exist
    return [package_name.replace("-", "_")]


def check_import_in_env(prefix: Path, import_name: str) -> tuple[bool, str]:
    """
    Check if a module can be imported in the target environment.

    Runs python -c 'import <module>' in the environment.
    Returns (success: bool, error_message: str).
    """
    python = prefix / get_python_short_path()
    result = subprocess.run(
        [str(python), "-c", f"import {import_name}"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return (result.returncode == 0, result.stderr)


@pytest.mark.qa
def test_qa_install_and_import(package_name: str, tmp_env, conda_cli, request):
    """
    QA test: Install PyPI package via conda pypi and verify import.

    This test performs two phases:
    1. Install: Run conda pypi install for the package
    2. Import: Verify the package can be imported in Python

    Both phases report detailed error messages on failure.
    """
    # Skip if no packages were specified via CLI
    if not request.config.getoption("--qa-packages"):
        pytest.skip("No packages specified via --qa-packages")

    # Phase 1: Install package
    with tmp_env("python=3.11") as prefix:
        out, err, rc = conda_cli(
            "pypi",
            "--yes",
            "install",
            "--ignore-channels",
            "--prefix",
            prefix,
            package_name,
        )

        # Check install success
        assert rc == 0, f"Install failed for {package_name}:\n{err}\n{out}"

        # Phase 2: Determine import names and test imports
        import_names = get_import_names_from_metadata(prefix, package_name)

        # Try importing all top-level modules
        import_results = []
        for import_name in import_names:
            success, error_msg = check_import_in_env(prefix, import_name)
            import_results.append((import_name, success, error_msg))

        # Report results
        successful_imports = [name for name, success, _ in import_results if success]
        failed_imports = [(name, msg) for name, success, msg in import_results if not success]

        # Assert at least one module imported successfully
        assert successful_imports, (
            f"Import failed for {package_name}. "
            f"Tried: {import_names}. "
            f"Failures:\n" + "\n".join(f"  {name}: {msg}" for name, msg in failed_imports)
        )
