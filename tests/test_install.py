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
        ("numpy", "numpy", "conda-forge"),
        ("numpy=1.20", "numpy=1.20", "conda-forge"),
        # build was originally published as build in conda-forge
        # and later renamed to python-build; conda-forge::build is
        # only available til 0.7, but conda-forge::python-build has 1.x
        ("build>=1", "python-build>=1", "conda-forge"),
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
        assert MatchSpec(pypi_spec).name in out or MatchSpec(conda_spec).name in out
        pd = PrefixData(str(prefix), pip_interop_enabled=channel == "pypi")
        records = list(pd.query(conda_spec))
        assert len(records) == 1
        assert records[0].channel.name == channel
        
