from __future__ import annotations

import os
import sys
from pathlib import Path
from collections.abc import Iterable
from subprocess import run

import pytest
from conda.core.prefix_data import PrefixData
from conda.models.match_spec import MatchSpec
from conda.testing.fixtures import TmpEnvFixture, CondaCLIFixture

from conda_pypi.python_paths import get_env_python, get_env_site_packages


@pytest.mark.skip(reason="Migrating to alternative install method using conda pupa")
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
    # Skip grayskull tests on Python < 3.10 due to grayskull dependency issues
    if backend == "grayskull" and sys.version_info < (3, 10):
        pytest.skip(
            "Grayskull requires Python 3.10+ due to union type annotations in dependencies"
        )

    conda_spec = conda_spec or pypi_spec
    with tmp_env("python=3.9", "pip") as prefix:
        out, err, rc = conda_cli(
            "pypi",
            "-p",
            prefix,
            "--yes",
            "install",
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
            pd = PrefixData(str(prefix), interoperability=True)
            records = list(pd.query(pypi_spec))
        else:
            pd = PrefixData(str(prefix), interoperability=False)
            records = list(pd.query(conda_spec))
        assert len(records) == 1
        assert records[0].channel.name == channel


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
            assert "All packages are already installed." in out + err


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
                [
                    get_env_python(prefix),
                    "-mpip",
                    "install",
                    "--isolated",
                    "--break-system-packages",
                    *specs,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            print(p.stdout)
            print(p.stderr, file=sys.stderr)
            assert p.returncode == 0
        else:
            out, err, rc = conda_cli("pypi", "--prefix", prefix, "--yes", "install", *specs)
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
    # PyPI metadata can vary between installs (checksums, platform tags, etc.)
    # so we check that the core package list is the same
    lines1 = [line for line in out.splitlines() if line.startswith(("https://", "# pypi:"))]
    lines2 = [line for line in out2.splitlines() if line.startswith(("https://", "# pypi:"))]

    # Extract just the conda packages (should be identical)
    conda_lines1 = [line for line in lines1 if line.startswith("https://")]
    conda_lines2 = [line for line in lines2 if line.startswith("https://")]
    assert sorted(conda_lines1) == sorted(conda_lines2)

    # For PyPI packages, just check package names and versions are the same
    # (ignoring metadata like checksums, platform tags, etc.)
    def extract_pypi_pkg_version(line):
        if line.startswith("# pypi: "):
            # Extract just "package==version" part
            pkg_part = line.split()[2]  # "package==version"
            return pkg_part.split("==")[0:2]  # ["package", "version"]
        return None

    pypi_pkgs1 = sorted(
        [extract_pypi_pkg_version(line) for line in lines1 if line.startswith("# pypi:")]
    )
    pypi_pkgs2 = sorted(
        [extract_pypi_pkg_version(line) for line in lines2 if line.startswith("# pypi:")]
    )
    assert pypi_pkgs1 == pypi_pkgs2


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
        print(out)
        print(err, file=sys.stderr)
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
