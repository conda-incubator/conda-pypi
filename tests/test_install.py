import sys

import pytest

from conda.core.prefix_data import PrefixData
from conda.models.match_spec import MatchSpec
from conda.testing import CondaCLIFixture, TmpEnvFixture

from conda_pip.dependencies import BACKENDS


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
        # these won't be ever published in conda-forge, I guess
        ("aaargh", None, "pypi"),
        ("5-exercise-upload-to-pypi", None, "pypi"),
    ],
)
def test_conda_pip_install(
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


@pytest.mark.parametrize("spec", ("pytest-cov", "pytest_cov", "PyTest-Cov"))
def test_spec_normalization(
    tmp_env: TmpEnvFixture,
    conda_cli: CondaCLIFixture,
    spec: str,
):
    with tmp_env("python=3.9", "pip", "pytest-cov") as prefix:
        out, err, rc = conda_cli("pip", "-p", prefix, "--yes", "install", spec)
        print(out)
        print(err, file=sys.stderr)
        assert rc == 0
        assert "All packages are already installed." in out + err
