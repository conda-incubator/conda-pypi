import sys

from conda.testing import CondaCLIFixture, TmpEnvFixture
from conda.testing.integration import package_is_installed

def test_conda_pip_install_numpy(tmp_env: TmpEnvFixture, conda_cli: CondaCLIFixture):
    with tmp_env("python=3.9", "pip") as prefix:
        out, err, rc = conda_cli(
            "pip",
            "-p",
            prefix,
            "--yes",
            "install",
            "numpy",
        )
        print(out)
        print(err, file=sys.stderr)
        assert rc == 0
        assert "numpy" in out
        assert package_is_installed(str(prefix), "numpy")
