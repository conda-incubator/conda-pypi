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

from conda_pypi.translate import pypi_to_conda_name
from conda_pypi.python_paths import get_env_python, get_env_site_packages


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
        pd = PrefixData(str(prefix), pip_interop_enabled=True)
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
                "All packages are already installed." in out + err
                or "is already installed; ignoring" in out + err
            )


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
        if pure_pip:
            assert "# pypi: requests" in out
            if md5:
                assert "--record-checksum=md5:" in out

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
    if pure_pip:
        assert "Preparing PyPI transaction" in p.stdout
        assert "Executing PyPI transaction" in p.stdout
        assert "Verifying PyPI transaction" in p.stdout

    out2, err2, rc2 = conda_cli("list", "--explicit", *md5, "--prefix", tmp_path / "env")
    print(out2)
    print(err2, file=sys.stderr)
    assert rc2 == 0
    assert sorted(out2.splitlines()) == sorted(out.splitlines())


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
    os.chdir(tmp_path)
    with tmp_env("python=3.9", "pip") as prefix:
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
        sp = get_env_site_packages(prefix)
        editable_pth = list(sp.glob(f"__editable__.{name}-*.pth"))
        assert len(editable_pth) == 1
        pth_contents = editable_pth[0].read_text().strip()
        assert pth_contents.startswith((str(tmp_path / "src"), f"import __editable___{name}"))
