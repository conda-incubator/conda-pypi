from __future__ import annotations

import sys
from pathlib import Path

import pytest
from conda.testing import CondaCLIFixture, TmpEnvFixture


def test_convert_basic_package(
    tmp_env: TmpEnvFixture,
    conda_cli: CondaCLIFixture,
    tmp_path: Path,
):
    """Test basic convert functionality with a simple package."""
    with tmp_env("python=3.10", "pip") as prefix:
        output_dir = tmp_path / "converted_packages"

        out, err, rc = conda_cli(
            "pip",
            "-p",
            prefix,
            "--yes",
            "convert",
            "-d",
            str(output_dir),
            "packaging",
        )
        print("Convert output:")
        print(out)
        print(err, file=sys.stderr)

        # Should succeed
        assert rc == 0, "Convert command should succeed"

        # Should contain conversion messages
        assert (
            "Converting PyPI packages to .conda format" in out
        ), "Should show conversion progress"

        # Output directory should be created
        assert output_dir.exists(), "Output directory should be created"

        # Should have created .conda files in the output directory
        conda_files = list(output_dir.glob("*.conda"))
        assert len(conda_files) > 0, "Should have created at least one .conda file"


def test_convert_with_dest_option(
    tmp_env: TmpEnvFixture,
    conda_cli: CondaCLIFixture,
    tmp_path: Path,
):
    """Test convert command with custom destination directory."""
    with tmp_env("python=3.10", "pip") as prefix:
        custom_dest = tmp_path / "my_custom_packages"

        out, err, rc = conda_cli(
            "pip",
            "-p",
            prefix,
            "--yes",
            "convert",
            "--dest",
            str(custom_dest),
            "wheel",
        )
        print("Convert with custom dest output:")
        print(out)
        print(err, file=sys.stderr)

        # Should succeed
        assert rc == 0, "Convert with custom destination should succeed"

        # Should contain conversion messages
        assert (
            "Converting PyPI packages to .conda format" in out
        ), "Should show conversion progress"

        # Custom destination should be created
        assert custom_dest.exists(), "Custom destination directory should be created"

        # Should have created .conda files in the custom destination
        conda_files = list(custom_dest.glob("*.conda"))
        assert len(conda_files) > 0, "Should have created at least one .conda file"


def test_convert_override_channels(
    tmp_env: TmpEnvFixture,
    conda_cli: CondaCLIFixture,
    tmp_path: Path,
):
    """Test convert command with --override-channels option."""
    with tmp_env("python=3.10", "pip") as prefix:
        output_dir = tmp_path / "override_packages"

        out, err, rc = conda_cli(
            "pip",
            "-p",
            prefix,
            "--yes",
            "convert",
            "-d",
            str(output_dir),
            "--override-channels",
            "six",
        )
        print("Convert with override channels output:")
        print(out)
        print(err, file=sys.stderr)

        # Should succeed
        assert rc == 0, "Convert with override channels should succeed"

        # Should contain conversion messages
        assert (
            "Converting PyPI packages to .conda format" in out
        ), "Should show conversion progress"

        # Should have created .conda files in the output directory
        conda_files = list(output_dir.glob("*.conda"))
        assert len(conda_files) > 0, "Should have created at least one .conda file"


def test_convert_multiple_packages(
    tmp_env: TmpEnvFixture,
    conda_cli: CondaCLIFixture,
    tmp_path: Path,
):
    """Test converting multiple packages at once."""
    with tmp_env("python=3.10", "pip") as prefix:
        output_dir = tmp_path / "multi_packages"

        out, err, rc = conda_cli(
            "pip",
            "-p",
            prefix,
            "--yes",
            "convert",
            "-d",
            str(output_dir),
            "packaging",
            "wheel",
        )
        print("Convert multiple packages output:")
        print(out)
        print(err, file=sys.stderr)

        # Should succeed
        assert rc == 0, "Convert multiple packages should succeed"

        # Should show conversion progress
        assert (
            "Converting PyPI packages to .conda format" in out
        ), "Should show conversion progress"

        # Should have created .conda files for multiple packages
        conda_files = list(output_dir.glob("*.conda"))
        assert len(conda_files) >= 2, "Should have created at least two .conda files"


def test_convert_no_packages_error(
    tmp_env: TmpEnvFixture,
    conda_cli: CondaCLIFixture,
    tmp_path: Path,
):
    """Test that convert command fails when no packages are provided."""
    from conda.exceptions import ArgumentError

    with tmp_env("python=3.10", "pip") as prefix:
        output_dir = tmp_path / "no_packages"

        with pytest.raises(ArgumentError, match="No packages requested"):
            out, err, rc = conda_cli(
                "pip",
                "-p",
                prefix,
                "--yes",
                "convert",
                "-d",
                str(output_dir),
            )


def test_convert_nonexistent_package(
    tmp_env: TmpEnvFixture,
    conda_cli: CondaCLIFixture,
    tmp_path: Path,
):
    """Test convert command with a package that doesn't exist."""
    with tmp_env("python=3.10", "pip") as prefix:
        output_dir = tmp_path / "nonexistent_packages"

        out, err, rc = conda_cli(
            "pip",
            "-p",
            prefix,
            "--yes",
            "convert",
            "-d",
            str(output_dir),
            "this-package-definitely-does-not-exist-12345",
        )
        print("Convert nonexistent package output:")
        print(out)
        print(err, file=sys.stderr)

        # The command might succeed but with warnings, or it might fail
        # Either way, there should be some indication of the issue
        error_text = err.lower()  # Error messages typically go to stderr

        # Check for various error indicators
        has_error_indication = any(
            phrase in error_text
            for phrase in [
                "not found",
                "could not find",
                "no matching distribution",
                "error",
                "failed",
                "warning",
                "404",
            ]
        )

        # If the command succeeded, it should at least show some warning or indication
        if rc == 0:
            assert has_error_indication, "Should have some indication about the missing package"
        else:
            # If it failed, that's also acceptable behavior
            assert (
                has_error_indication
            ), "Should have appropriate error message about the missing package"


def test_convert_default_destination(
    tmp_env: TmpEnvFixture,
    conda_cli: CondaCLIFixture,
    tmp_path: Path,
):
    """Test convert command with default destination (current directory)."""
    with tmp_env("python=3.10", "pip") as prefix:
        # Change to tmp_path to test default destination
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)

            out, err, rc = conda_cli(
                "pip",
                "-p",
                prefix,
                "--yes",
                "convert",
                "setuptools",
            )
            print("Convert with default destination output:")
            print(out)
            print(err, file=sys.stderr)

            # Should succeed
            assert rc == 0, "Convert with default destination should succeed"

            # Should contain conversion messages
            assert (
                "Converting PyPI packages to .conda format" in out
            ), "Should show conversion progress"

            # Should have created .conda files in the current directory
            conda_files = list(tmp_path.glob("*.conda"))
            assert len(conda_files) > 0, "Should have created at least one .conda file"

        finally:
            os.chdir(original_cwd)


def test_convert_quiet_mode(
    tmp_env: TmpEnvFixture,
    conda_cli: CondaCLIFixture,
    tmp_path: Path,
):
    """Test convert command in quiet mode."""
    with tmp_env("python=3.10", "pip") as prefix:
        output_dir = tmp_path / "quiet_packages"

        out, err, rc = conda_cli(
            "pip",
            "-p",
            prefix,
            "--quiet",
            "--yes",
            "convert",
            "-d",
            str(output_dir),
            "tomli",
        )
        print("Convert quiet mode output:")
        print(out)
        print(err, file=sys.stderr)

        # Should succeed
        assert rc == 0, "Convert in quiet mode should succeed"

        # In quiet mode, the spinner message should be suppressed
        assert (
            "Converting PyPI packages to .conda format" not in out
        ), "Quiet mode should suppress progress messages"

        # The output directory should still be created
        assert output_dir.exists(), "Output directory should be created"

        # The command should still work (we can verify by checking that .conda files are created)
        conda_files = list(output_dir.glob("*.conda"))
        assert len(conda_files) > 0, "Conversion process should create .conda files"


def test_convert_with_version_spec(
    tmp_env: TmpEnvFixture,
    conda_cli: CondaCLIFixture,
    tmp_path: Path,
):
    """Test convert command with version specifications."""
    with tmp_env("python=3.10", "pip") as prefix:
        output_dir = tmp_path / "versioned_packages"

        out, err, rc = conda_cli(
            "pip",
            "-p",
            prefix,
            "--yes",
            "convert",
            "-d",
            str(output_dir),
            "packaging>=20.0",
        )
        print("Convert with version spec output:")
        print(out)
        print(err, file=sys.stderr)

        # Should succeed
        assert rc == 0, "Convert with version spec should succeed"

        # Should contain conversion messages
        assert (
            "Converting PyPI packages to .conda format" in out
        ), "Should show conversion progress"

        # Output directory should be created
        assert output_dir.exists(), "Output directory should be created"

        # Should have created .conda files in the output directory
        conda_files = list(output_dir.glob("*.conda"))
        assert len(conda_files) > 0, "Should have created at least one .conda file"
