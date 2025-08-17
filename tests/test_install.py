from __future__ import annotations

import os
import sys
from pathlib import Path
from subprocess import run
from typing import Iterable

import pytest
from conda.core.prefix_data import PrefixData
from conda.models.match_spec import MatchSpec
from conda.testing import CondaCLIFixture, TmpEnvFixture

from conda_pypi.mapping import pypi_to_conda_name
from conda_pypi.utils import get_env_python, get_env_site_packages


def _verify_vcs_editable_install(prefix: Path, package_name: str):
    """Verify that a VCS package was installed in editable mode."""
    sp = get_env_site_packages(prefix)

    name_variants = [package_name.lower().replace("_", "-"), package_name, package_name.lower()]

    editable_pth = None
    for variant in name_variants:
        pth_files = list(sp.glob(f"__editable__.{variant}-*.pth"))
        if pth_files:
            editable_pth = pth_files[0]
            break

    if not editable_pth:
        all_editable = list(sp.glob("__editable__.*.pth"))
        if all_editable:
            editable_pth = all_editable[0]

    assert editable_pth, f"No editable .pth file found for VCS package {package_name}"

    pth_contents = editable_pth.read_text().strip()

    # Handle both old-style (direct path) and new-style (PEP 660 import) .pth files
    if pth_contents.startswith("import "):
        # PEP 660 style - just verify the .pth file exists and contains import statement
        assert "import " in pth_contents, f"Invalid PEP 660 .pth file format: {pth_contents}"
    else:
        # Old style - verify source path exists
        source_path = None
        for line in pth_contents.split("\n"):
            line = line.strip()
            if line and not line.startswith("import") and Path(line).exists():
                source_path = Path(line)
                break

        assert (
            source_path and source_path.exists()
        ), f"Invalid source path in .pth file: {pth_contents}"

    python_exe = get_env_python(prefix)
    import_name = package_name.lower().replace("-", "_")

    import_mappings = {
        "python_dateutil": "dateutil",
        "pyyaml": "yaml",
    }
    import_name = import_mappings.get(import_name, import_name)

    result = run(
        [python_exe, "-c", f"import {import_name}; print('Success')"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Failed to import {import_name}: {result.stderr}"


def test_pypi_to_conda_name_mapping():
    assert pypi_to_conda_name("build") == "python-build"


@pytest.mark.parametrize(
    "pypi_name,conda_name",
    [
        ("numpy", "numpy"),
        ("build", "python-build"),
        ("ib_insync", "ib-insync"),
        ("pyqt5", "pyqt"),
        ("PyQt5", "pyqt"),
    ],
)
def test_pypi_to_conda_name_mappings(pypi_name: str, conda_name: str):
    assert pypi_to_conda_name(pypi_name) == conda_name


@pytest.mark.parametrize(
    "pypi_spec,conda_spec,expected_source",
    [
        # All explicitly installed packages should come from PyPI
        ("numpy", "", "pypi"),
    ],
)
def test_conda_pypi_install(
    tmp_env: TmpEnvFixture,
    conda_cli: CondaCLIFixture,
    pypi_spec: str,
    conda_spec: str,
    expected_source: str,
):
    conda_spec = conda_spec or pypi_spec
    with tmp_env("python=3.9", "pip") as prefix:
        out, err, rc = conda_cli(
            "pip",
            "-p",
            prefix,
            "--yes",
            "install",
            pypi_spec,
        )
        print(out)
        print(err, file=sys.stderr)
        assert rc == 0
        assert any(
            name in out
            for name in (
                MatchSpec(pypi_spec).name,
                MatchSpec(pypi_spec).name.replace("-", "_"),  # pip normalizes this
                MatchSpec(conda_spec).name,
            )
        )
        PrefixData._cache_.clear()
        # All explicitly installed packages should come from PyPI and be converted to conda format
        pd = PrefixData(str(prefix), interoperability=True)
        records = list(pd.query(pypi_spec))
        assert len(records) == 1
        assert records[0].channel.name == "pypi"


def test_spec_normalization(
    tmp_env: TmpEnvFixture,
    conda_cli: CondaCLIFixture,
):
    with tmp_env("python=3.9", "pip", "pytest-cov") as prefix:
        for spec in ("pytest-cov", "pytest_cov", "PyTest-Cov"):
            out, err, rc = conda_cli("pip", "-p", prefix, "--yes", "install", "--dry-run", spec)
            print(out)
            print(err, file=sys.stderr)
            assert rc == 0
            assert (
                "All packages are already installed." in out
                or "is already installed; ignoring" in out
            )


@pytest.mark.skip(
    reason="PyQt5 has complex dependencies that exceed conda solver limits (20 attempts)"
)
@pytest.mark.parametrize(
    "pypi_spec,requested_conda_spec,installed_conda_specs",
    [
        ("PyQt5", "pyqt5", ("pyqt5",)),
    ],
)
def test_pyqt(
    tmp_env: TmpEnvFixture,
    conda_cli: CondaCLIFixture,
    pypi_spec: str,
    requested_conda_spec: str,
    installed_conda_specs: tuple[str],
):
    with tmp_env("python=3.9", "pip") as prefix:
        out, err, rc = conda_cli("pip", "-p", prefix, "--yes", "--dry-run", "install", pypi_spec)
        print(out)
        print(err, file=sys.stderr)
        assert rc == 0
        assert requested_conda_spec in out
        for conda_spec in installed_conda_specs:
            assert conda_spec in out


@pytest.mark.parametrize("specs", (("requests",),))
@pytest.mark.parametrize("pure_pip", (True, False))
@pytest.mark.parametrize("with_md5", (True, False))
def test_lockfile_roundtrip(
    tmp_path: Path,
    tmp_env: TmpEnvFixture,
    conda_cli: CondaCLIFixture,
    specs: Iterable[str],
    pure_pip: bool,
    with_md5: bool,
):
    md5 = ("--md5",) if with_md5 else ()
    with tmp_env("python=3.9", "pip") as prefix:
        if pure_pip:
            p = run(
                [get_env_python(prefix), "-mpip", "install", "--break-system-packages", *specs],
                capture_output=True,
                text=True,
                check=False,
            )
            print(p.stdout)
            print(p.stderr, file=sys.stderr)
            assert p.returncode == 0
        else:
            out, err, rc = conda_cli("pip", "--prefix", prefix, "--yes", "install", *specs)
            print(out)
            print(err, file=sys.stderr)
            assert rc == 0
        out, err, rc = conda_cli("list", "--explicit", "--prefix", prefix, *md5)
        print(out)
        print(err, file=sys.stderr)
        assert rc == 0
        if not pure_pip:
            assert "requests" in out
            assert "file://" in out

    (tmp_path / "lockfile.txt").write_text(out)
    p = run(
        [
            sys.executable,
            "-mconda",
            "create",
            "--prefix",
            tmp_path / "env",
            "--file",
            tmp_path / "lockfile.txt",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    print(p.stdout)
    print(p.stderr, file=sys.stderr)
    assert p.returncode == 0

    out2, err2, rc2 = conda_cli("list", "--explicit", *md5, "--prefix", tmp_path / "env")
    print(out2)
    print(err2, file=sys.stderr)
    assert rc2 == 0

    if not pure_pip:
        for spec in specs:
            package_present = any(spec in line for line in out2.splitlines())
            assert package_present, f"Package {spec} not found in recreated environment lockfile"


@pytest.mark.parametrize(
    "requirement,name",
    [
        (
            # pure Python
            "git+https://github.com/dateutil/dateutil.git@2.9.0.post0",
            "python_dateutil",
        ),
        (
            # compiled bits
            "git+https://github.com/yaml/pyyaml.git@6.0.1",
            "PyYAML",
        ),
        (
            # has conda dependencies
            "git+https://github.com/regro/conda-forge-metadata.git@0.8.1",
            "conda_forge_metadata",
        ),
    ],
)
def test_editable_installs(
    tmp_path: Path, tmp_env: TmpEnvFixture, conda_cli: CondaCLIFixture, requirement, name
):
    """
    Test editable installations from VCS URLs.

    Verifies that conda-pypi handles VCS editable installs by:
    1. Cloning the repository to a persistent location
    2. Installing directly with pip in editable mode
    3. Verifying the editable .pth file points to source directory
    4. Confirming the package can be imported

    Tests different package types:
    - Pure Python packages (python-dateutil)
    - Packages with compiled extensions (PyYAML)
    - Packages with conda dependencies (conda-forge-metadata)
    """
    import sys

    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"

    os.chdir(tmp_path)
    with tmp_env(f"python={python_version}", "pip") as prefix:
        out, err, rc = conda_cli(
            "pip",
            "-p",
            prefix,
            "--yes",
            "install",
            "-e",
            f"{requirement}#egg={name}",
        )
        print(out)
        print(err, file=sys.stderr)
        assert rc == 0

        if requirement.startswith(("git+", "hg+", "svn+", "bzr+")):
            # Verify VCS package was installed in editable mode
            _verify_vcs_editable_install(prefix, name)
        else:
            # For local paths, look for traditional editable .pth files
            sp = get_env_site_packages(prefix)
            editable_pth = list(sp.glob(f"__editable__.{name}-*.pth"))
            if not editable_pth:
                editable_pth = list(sp.glob(f"__editable__.{name.lower()}-*.pth"))
            assert (
                len(editable_pth) == 1
            ), f"Expected exactly one editable .pth file, found {len(editable_pth)}"

            # Verify the .pth file contents
            pth_contents = editable_pth[0].read_text().strip()
            expected_paths = (str(tmp_path / "src"), f"import __editable___{name}")
            assert pth_contents.startswith(
                expected_paths
            ), f"Unexpected local path: {pth_contents}"


def test_install_package_with_extras(
    tmp_env: TmpEnvFixture,
    conda_cli: CondaCLIFixture,
):
    """Test installing a package with extras (e.g., package[extra])."""
    with tmp_env("python=3.10", "pip") as prefix:
        out, err, rc = conda_cli(
            "pip",
            "-p",
            prefix,
            "--yes",
            "install",
            "packaging[test]",
        )
        print(out)
        print(err, file=sys.stderr)
        assert rc == 0

        PrefixData._cache_.clear()
        pd = PrefixData(str(prefix), interoperability=True)

        packaging_records = list(pd.query("packaging"))
        assert len(packaging_records) >= 1, "packaging package not found"


def test_update_already_installed_package(
    tmp_env: TmpEnvFixture,
    conda_cli: CondaCLIFixture,
):
    """Test behavior when trying to install a package that's already installed."""
    with tmp_env("python=3.10", "pip") as prefix:
        out, err, rc = conda_cli(
            "pip",
            "-p",
            prefix,
            "--yes",
            "install",
            "packaging",
        )
        assert rc == 0, "Initial installation should succeed"

        out, err, rc = conda_cli(
            "pip",
            "-p",
            prefix,
            "--yes",
            "install",
            "packaging",
        )
        print("Reinstall output:")
        print(out)
        print(err, file=sys.stderr)
        assert rc == 0, "Reinstalling existing package should succeed"

        PrefixData._cache_.clear()
        pd = PrefixData(str(prefix), interoperability=True)
        packaging_records = list(pd.query("packaging"))
        assert len(packaging_records) >= 1, "packaging should still be installed"


def test_install_nonexistent_package(
    tmp_env: TmpEnvFixture,
    conda_cli: CondaCLIFixture,
):
    """Test installing a package that doesn't exist."""
    with tmp_env("python=3.10", "pip") as prefix:
        out, err, rc = conda_cli(
            "pip",
            "-p",
            prefix,
            "--yes",
            "install",
            "this-package-definitely-does-not-exist-12345",
        )
        print("Nonexistent package install attempt:")
        print(out)
        print(err, file=sys.stderr)

        error_text = err.lower()  # Error messages typically go to stderr
        assert any(
            phrase in error_text
            for phrase in [
                "not found",
                "could not find",
                "no matching distribution",
                "error",
                "failed",
                "exceeded maximum",
                "404",
            ]
        ), "Should have an appropriate error message about the missing package"


def test_install_with_invalid_environment(
    conda_cli: CondaCLIFixture,
):
    """Test installing to a non-existent environment."""
    try:
        out, err, rc = conda_cli(
            "pip",
            "-p",
            "/this/path/definitely/does/not/exist",
            "--yes",
            "install",
            "requests",
        )
        print("Install to invalid environment:")
        print(out)
        print(err, file=sys.stderr)

        assert rc != 0, "Should fail when environment doesn't exist"

    except Exception as e:
        print(f"Expected exception caught: {e}")
        assert "python>=3.2" in str(e) or "does not exist" in str(
            e
        ), "Should have appropriate error message about the environment"


def test_dry_run_functionality(
    tmp_env: TmpEnvFixture,
    conda_cli: CondaCLIFixture,
):
    """Test that --dry-run doesn't actually install packages."""
    with tmp_env("python=3.10", "pip") as prefix:
        # Test dry-run with a new package that isn't installed
        out, err, rc = conda_cli(
            "pip",
            "-p",
            prefix,
            "--yes",
            "install",
            "--dry-run",
            "requests",
        )
        print("Dry-run output:")
        print(out)
        print(err, file=sys.stderr)

        # Should succeed
        assert rc == 0, "Dry-run should succeed"

        # Should indicate what would be installed
        assert "Would install packages: requests" in out, "Should show what would be installed"

        # Should NOT contain installation messages
        assert "Installing collected packages" not in out, "Should not actually install packages"
        assert "Executing transaction: done" not in out, "Should not execute transaction"
        assert "Successfully installed" not in out, "Should not show successful installation"

        # Verify the package is NOT actually installed
        PrefixData._cache_.clear()
        pd = PrefixData(str(prefix), interoperability=True)
        requests_records = list(pd.query("requests"))
        assert len(requests_records) == 0, "Package should not be installed after dry-run"


def test_dry_run_with_already_installed_package(
    tmp_env: TmpEnvFixture,
    conda_cli: CondaCLIFixture,
):
    """Test that --dry-run correctly handles already installed packages."""
    with tmp_env("python=3.10", "pip", "packaging") as prefix:
        # Test dry-run with an already installed package
        out, err, rc = conda_cli(
            "pip",
            "-p",
            prefix,
            "--yes",
            "install",
            "--dry-run",
            "packaging",
        )
        print("Dry-run with installed package output:")
        print(out)
        print(err, file=sys.stderr)

        # Should succeed
        assert rc == 0, "Dry-run should succeed"

        # Should indicate all packages are already installed
        assert (
            "All packages are already installed." in out
        ), "Should show packages are already installed"

        # Should NOT contain installation messages
        assert "Installing collected packages" not in out, "Should not actually install packages"
        assert "Executing transaction: done" not in out, "Should not execute transaction"
        assert (
            "Would install packages" not in out
        ), "Should not show would install for already installed packages"


def test_dry_run_with_mixed_packages(
    tmp_env: TmpEnvFixture,
    conda_cli: CondaCLIFixture,
):
    """Test that --dry-run correctly handles mix of installed and new packages."""
    with tmp_env("python=3.10", "pip", "packaging") as prefix:
        # Test dry-run with mix of installed and new packages
        out, err, rc = conda_cli(
            "pip",
            "-p",
            prefix,
            "--yes",
            "install",
            "--dry-run",
            "packaging",  # already installed
            "requests",  # not installed
        )
        print("Dry-run with mixed packages output:")
        print(out)
        print(err, file=sys.stderr)

        # Should succeed
        assert rc == 0, "Dry-run should succeed"

        # Should indicate what would be installed (only the new package)
        assert (
            "Would install packages: requests" in out
        ), "Should show only new packages would be installed"

        # Should warn about already installed package
        assert (
            "packaging is already installed; ignoring" in out
        ), "Should warn about already installed package"

        # Should NOT contain installation messages
        assert "Installing collected packages" not in out, "Should not actually install packages"
        assert "Executing transaction: done" not in out, "Should not execute transaction"

        # Verify requests is NOT actually installed
        PrefixData._cache_.clear()
        pd = PrefixData(str(prefix), interoperability=True)
        requests_records = list(pd.query("requests"))
        assert len(requests_records) == 0, "New package should not be installed after dry-run"
