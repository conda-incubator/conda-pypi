from __future__ import annotations

import sys
from pathlib import Path
from subprocess import run
from typing import Iterable

import pytest
from conda.core.prefix_data import PrefixData
from conda.models.match_spec import MatchSpec
from conda.testing import CondaCLIFixture, TmpEnvFixture

from conda_pypi.dependencies import NAME_MAPPINGS, BACKENDS, _pypi_spec_to_conda_spec
from conda_pypi.utils import get_env_python


@pytest.mark.parametrize("source", NAME_MAPPINGS.keys())
def test_mappings_one_by_one(source: str):
    assert _pypi_spec_to_conda_spec("build", sources=(source,)) == "python-build"


@pytest.mark.parametrize(
    "pypi_spec,conda_spec",
    [
        ("numpy", "numpy"),
        ("build", "python-build"),
        ("ib_insync", "ib-insync"),
        ("pyqt5", "pyqt>=5.0.0,<6.0.0.0dev0"),
        ("PyQt5", "pyqt>=5.0.0,<6.0.0.0dev0"),
    ],
)
def test_mappings_fallback(pypi_spec: str, conda_spec: str):
    assert MatchSpec(_pypi_spec_to_conda_spec(pypi_spec)) == MatchSpec(conda_spec)


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize(
    "pypi_spec,conda_spec,channel",
    [
        ("numpy", "", "conda-forge"),
        ("numpy=1.20", "", "conda-forge"),
        # build was originally published as build in conda-forge
        # and later renamed to python-build; conda-forge::build is
        # only available til 0.7, but conda-forge::python-build has 1.x
        ("build>=1", "python-build>=1", "conda-forge"),
        # ib-insync is only available with dashes, not with underscores
        ("ib_insync", "ib-insync", "conda-forge"),
        # these won't be ever published in conda-forge, I guess
        ("aaargh", None, "pypi"),
        ("5-exercise-upload-to-pypi", None, "pypi"),
    ],
)
def test_conda_pypi_install(
    tmp_env: TmpEnvFixture,
    conda_cli: CondaCLIFixture,
    pypi_spec: str,
    conda_spec: str,
    channel: str,
    backend: str,
):
    conda_spec = conda_spec or pypi_spec
    with tmp_env("python=3.9", "pip") as prefix:
        out, err, rc = conda_cli(
            "pip",
            "-p",
            prefix,
            "--yes",
            "install",
            "--backend",
            backend,
            pypi_spec,
        )
        print(out)
        print(err, file=sys.stderr)
        assert rc == 0
        # One these package names will be mentioned:
        assert any(
            name in out
            for name in (
                MatchSpec(pypi_spec).name,
                MatchSpec(pypi_spec).name.replace("-", "_"),  # pip normalizes this
                MatchSpec(conda_spec).name,
            )
        )
        PrefixData._cache_.clear()
        if channel == "pypi":
            pd = PrefixData(str(prefix), pip_interop_enabled=True)
            records = list(pd.query(pypi_spec))
        else:
            pd = PrefixData(str(prefix), pip_interop_enabled=False)
            records = list(pd.query(conda_spec))
        assert len(records) == 1
        assert records[0].channel.name == channel


def test_spec_normalization(
    tmp_env: TmpEnvFixture,
    conda_cli: CondaCLIFixture,
):
    with tmp_env("python=3.9", "pip", "pytest-cov") as prefix:
        for spec in ("pytest-cov", "pytest_cov", "PyTest-Cov"):
            out, err, rc = conda_cli("pip", "--dry-run", "-p", prefix, "--yes", "install", spec)
            print(out)
            print(err, file=sys.stderr)
            assert rc == 0
            assert "All packages are already installed." in out + err


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
