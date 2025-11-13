"""
Test that wheel files installed via conda-pypi create JSON files in conda-meta/
with the correct filename format: name-version-build.json
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conda.core.prefix_data import PrefixData
from conda.testing.fixtures import CondaCLIFixture, TmpEnvFixture


def test_extract_whl_sets_fn_correctly(
    pypi_demo_package_wheel_path: Path,
    tmp_path: Path,
):
    """
    Test that extract_whl_as_conda_pkg sets the fn field correctly in index.json.
    This is a unit test that directly tests the metadata creation.
    """
    from conda_pypi.pre_command.extract_whl import extract_whl_as_conda_pkg

    extract_whl_as_conda_pkg(str(pypi_demo_package_wheel_path), str(tmp_path))

    # Check that index.json was created with correct fn field
    index_json_path = tmp_path / "info" / "index.json"
    assert index_json_path.exists(), f"index.json should exist at {index_json_path}"

    with open(index_json_path) as f:
        index_data = json.load(f)

    # Verify fn field is set correctly with build string and .whl extension
    # Note: source.distribution returns the Python package name (with underscores),
    # so fn will be "demo_package-0.1.0-pypi_0.whl" not "demo-package-0.1.0-pypi_0.whl"
    assert "fn" in index_data, "index.json should contain 'fn' field"
    # The fn field should include the build string and .whl extension
    assert index_data["fn"].endswith("-pypi_0.whl"), (
        f"fn should end with '-pypi_0.whl', got: {index_data['fn']}"
    )
    assert ".whl" in index_data["fn"], (
        f"fn should include .whl extension, got: {index_data['fn']}"
    )
    # Verify the format is name-version-build.whl
    fn_parts = index_data["fn"].replace(".whl", "").rsplit("-", 2)
    assert len(fn_parts) == 3, (
        f"fn should have format name-version-build.whl, got: {index_data['fn']}"
    )
    fn_name, fn_version, fn_build = fn_parts
    assert fn_build == "pypi_0", f"build should be 'pypi_0', got: {fn_build}"

    # Verify other fields
    # The name field uses the Python package name (with underscores)
    assert index_data["name"] == "demo_package"
    assert index_data["version"] == "0.1.0"
    assert index_data["build"] == "pypi_0"
    assert index_data["build_number"] == 0


@pytest.mark.skip(reason="Integration test - requires full conda installation setup")
def test_wheel_conda_meta_json_filename_format(
    tmp_env: TmpEnvFixture,
    conda_cli: CondaCLIFixture,
    pypi_local_index: str,
):
    """
    Test that installing a wheel file creates a JSON file in conda-meta/
    with the correct filename format: name-version-build.json

    This ensures that the fn field is correctly set in index.json and that
    _get_json_fn() produces the expected filename format.
    """
    with tmp_env("python=3.10", "pip") as prefix:
        # Install a wheel package via conda-pypi
        out, err, rc = conda_cli(
            "pypi",
            "--prefix",
            prefix,
            "--yes",
            "install",
            "--override-channels",
            "--index-url",
            pypi_local_index,
            "demo-package",
        )
        assert rc == 0
        assert "Converted packages" in out or "All requested packages already installed" in out

        # Check that the conda-meta directory exists
        conda_meta_dir = Path(prefix) / "conda-meta"
        assert conda_meta_dir.exists(), f"conda-meta directory should exist at {conda_meta_dir}"

        # Find the JSON file for demo-package
        # Expected format: demo-package-0.1.0-pypi_0.json
        json_files = list(conda_meta_dir.glob("demo-package-*.json"))
        assert len(json_files) > 0, f"No JSON file found for demo-package in {conda_meta_dir}"

        # Find the correct JSON file (should match name-version-build.json format)
        expected_filename = "demo-package-0.1.0-pypi_0.json"
        json_file = conda_meta_dir / expected_filename
        assert json_file.exists(), (
            f"Expected JSON file {expected_filename} not found. "
            f"Found files: {[f.name for f in json_files]}"
        )

        # Read and verify the JSON content
        with open(json_file) as f:
            conda_meta_data = json.load(f)

        # Verify the fn field is correctly set (should include .whl extension)
        assert "fn" in conda_meta_data, "JSON file should contain 'fn' field"
        assert conda_meta_data["fn"] == "demo-package-0.1.0-pypi_0.whl", (
            f"Expected fn='demo-package-0.1.0-pypi_0.whl', got fn='{conda_meta_data['fn']}'"
        )

        # Verify other expected fields
        assert conda_meta_data["name"] == "demo-package"
        assert conda_meta_data["version"] == "0.1.0"
        assert conda_meta_data["build"] == "pypi_0"
        assert conda_meta_data["build_number"] == 0

        # Verify that PrefixData can load the record correctly
        prefix_data = PrefixData(prefix)
        record = prefix_data.get("demo-package")
        assert record is not None, "PrefixData should be able to load demo-package record"
        assert record.name == "demo-package"
        assert record.version == "0.1.0"
        assert record.build == "pypi_0"
        assert record.fn == "demo-package-0.1.0-pypi_0.whl"


@pytest.mark.skip(reason="Integration test - requires full conda installation setup")
def test_wheel_conda_meta_json_filename_with_different_package(
    tmp_env: TmpEnvFixture,
    conda_cli: CondaCLIFixture,
):
    """
    Test that installing a different wheel package (from PyPI) also creates
    the correct JSON filename format.
    """
    with tmp_env("python=3.11") as prefix:
        # Install a simple package from PyPI (e.g., certifi)
        out, err, rc = conda_cli(
            "pypi",
            "--prefix",
            prefix,
            "--yes",
            "install",
            "certifi",
        )
        assert rc == 0

        # Check conda-meta directory
        conda_meta_dir = Path(prefix) / "conda-meta"
        assert conda_meta_dir.exists()

        # Find certifi JSON file
        json_files = list(conda_meta_dir.glob("certifi-*.json"))
        assert len(json_files) > 0, f"No JSON file found for certifi in {conda_meta_dir}"

        # Verify the filename format matches name-version-build.json
        json_file = json_files[0]
        filename_parts = json_file.stem.rsplit("-", 2)  # Split from right to get name-version-build
        assert len(filename_parts) == 3, (
            f"JSON filename should have format name-version-build.json, "
            f"got: {json_file.name}"
        )
        name, version, build = filename_parts

        # Verify the JSON content matches the filename
        with open(json_file) as f:
            conda_meta_data = json.load(f)

        assert conda_meta_data["name"] == name
        assert conda_meta_data["version"] == version
        assert conda_meta_data["build"] == build
        # Verify fn field includes .whl extension
        assert conda_meta_data["fn"].endswith(".whl"), (
            f"fn field should end with .whl extension, got: {conda_meta_data['fn']}"
        )
        # Verify fn field matches expected format (without extension for comparison)
        expected_fn_base = f"{name}-{version}-{build}"
        assert conda_meta_data["fn"] == f"{expected_fn_base}.whl", (
            f"fn field should match filename format. "
            f"Expected: {expected_fn_base}.whl, got: {conda_meta_data['fn']}"
        )

