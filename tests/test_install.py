import sys

import pytest

from conda.testing import CondaCLIFixture, TmpEnvFixture
from conda.testing.integration import package_is_installed

from conda_pip.dependencies import BACKENDS

@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("spec", ["numpy", "numpy=1.20"])
def test_conda_pip_install_numpy(tmp_env: TmpEnvFixture, conda_cli: CondaCLIFixture, spec: str, backend: str):
    with tmp_env("python=3.9", "pip") as prefix:
        out, err, rc = conda_cli(
            "pip",
            "-p",
            prefix,
            "--yes",
            "install",
            "--backend",
            backend,
            spec,
        )
        print(out)
        print(err, file=sys.stderr)
        assert rc == 0
        assert spec in out
        assert package_is_installed(str(prefix), spec)
