from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from conda.testing.fixtures import TmpEnvFixture, CondaCLIFixture

from conda_pypi.python_paths import get_env_site_packages


def test_conda_pypi_install_basic(tmp_env: TmpEnvFixture, conda_cli: CondaCLIFixture):
    """Test basic conda pypi install functionality."""
    with tmp_env("python=3.11") as prefix:
        out, err, rc = conda_cli(
            "pypi",
            "-p",
            prefix,
            "--yes",
            "install",
            "numpy",
        )
        assert rc == 0


@pytest.mark.parametrize(
    "pypi_spec,expected_in_output",
    [
        ("certifi", "certifi"),
        ("tomli==2.0.1", "tomli"),
    ],
)
def test_conda_pypi_install_package_conversion(
    tmp_env: TmpEnvFixture,
    conda_cli: CondaCLIFixture,
    pypi_spec: str,
    expected_in_output: str,
):
    """Test that PyPI packages are correctly converted and installed."""
    with tmp_env("python=3.11") as prefix:
        out, err, rc = conda_cli(
            "pypi",
            "-p",
            prefix,
            "--yes",
            "install",
            pypi_spec,
        )
        assert rc == 0
        assert expected_in_output in out or "All requested packages already installed" in out


def test_conda_pypi_install_matchspec_parsing(tmp_env: TmpEnvFixture, conda_cli: CondaCLIFixture):
    """Test that MatchSpec parsing works correctly for various package specifications."""
    with tmp_env("python=3.11") as prefix:
        test_specs = [
            "numpy",
            "numpy>=1.20",
        ]

        for spec in test_specs:
            out, err, rc = conda_cli(
                "pypi",
                "-p",
                prefix,
                "--yes",
                "--dry-run",
                "install",
                spec,
            )
            assert rc == 0, f"Failed to parse spec '{spec}'"


def test_conda_pypi_install_requires_package_without_editable(
    tmp_env: TmpEnvFixture, conda_cli: CondaCLIFixture
):
    """Test that conda pypi install requires a package when not in editable mode."""
    with tmp_env("python=3.11") as prefix:
        with pytest.raises(SystemExit) as exc:
            conda_cli(
                "pypi",
                "-p",
                prefix,
                "install",
            )
        assert exc.value.code == 2


def test_conda_pypi_install_editable_without_packages_succeeds(
    tmp_env: TmpEnvFixture, conda_cli: CondaCLIFixture
):
    """Test that conda pypi install -e succeeds without additional packages."""
    with tmp_env("python=3.11") as prefix:
        out, err, rc = conda_cli(
            "pypi",
            "-p",
            prefix,
            "--yes",
            "install",
            "-e",
            str(Path(__file__).parent / "packages" / "has-build-dep"),
        )
        assert rc == 0


@pytest.mark.skip(reason="Migrating to alternative install method using conda pupa")
def test_spec_normalization(
    tmp_env: TmpEnvFixture,
    conda_cli: CondaCLIFixture,
):
    with tmp_env("python=3.9", "pip", "pytest-cov") as prefix:
        for spec in ("pytest-cov", "pytest_cov", "PyTest-Cov"):
            out, err, rc = conda_cli("pypi", "--dry-run", "-p", prefix, "--yes", "install", spec)
            print(out)
            print(err, file=sys.stderr)
            assert rc == 0
            assert "All requested packages already installed." in out


@pytest.mark.skip(reason="Migrating to alternative install method using conda pupa")
@pytest.mark.parametrize(
    "pypi_spec,requested_conda_spec,installed_conda_specs",
    [
        ("PyQt5", "pyqt[version='>=5.0.0,<6.0.0.0dev0']", ("pyqt-5", "qt-main-5")),
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
        out, err, rc = conda_cli("pypi", "-p", prefix, "--yes", "--dry-run", "install", pypi_spec)
        print(out)
        print(err, file=sys.stderr)
        assert rc == 0
        assert requested_conda_spec in out
        for conda_spec in installed_conda_specs:
            assert conda_spec in out


@pytest.mark.skip(reason="Migrating to alternative install method using conda pupa")
@pytest.mark.parametrize(
    "requirement,name",
    [
        pytest.param(
            # pure Python
            "git+https://github.com/dateutil/dateutil.git@2.9.0.post0",
            "python_dateutil",
            marks=pytest.mark.skip(reason="Fragile test with git repo state issues"),
        ),
        pytest.param(
            # compiled bits
            "git+https://github.com/yaml/pyyaml.git@6.0.1",
            "PyYAML",
            marks=pytest.mark.skip(reason="Editable install path detection issues"),
        ),
        pytest.param(
            # has conda dependencies
            "git+https://github.com/python-poetry/cleo.git@2.1.0",
            "cleo",
        ),
    ],
)
def test_editable_installs(
    tmp_path: Path, tmp_env: TmpEnvFixture, conda_cli: CondaCLIFixture, requirement, name
):
    os.chdir(tmp_path)
    with tmp_env("python=3.9", "pip") as prefix:
        out, err, rc = conda_cli(
            "pypi",
            "-p",
            prefix,
            "--yes",
            "install",
            "-e",
            f"{requirement}#egg={name}",
        )
        assert rc == 0
        sp = get_env_site_packages(prefix)
        editable_pth = list(sp.glob(f"__editable__.{name}-*.pth"))  # Modern pip format
        if not editable_pth:
            editable_pth = list(sp.glob(f"{name}.pth"))  # Older format

        assert len(editable_pth) == 1, (
            f"Expected 1 editable .pth file for {name}, found: {editable_pth}"
        )
        pth_contents = editable_pth[0].read_text().strip()
        src_path = tmp_path / "src"

        if not pth_contents.startswith(f"import __editable___{name}"):
            pth_path = Path(pth_contents)
            assert (
                src_path in pth_path.parents
                or src_path == pth_path
                or pth_path.is_relative_to(src_path)
            ), f"Expected {src_path} to be a parent of or equal to {pth_path}"
