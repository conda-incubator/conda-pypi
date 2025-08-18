import sys
from subprocess import run

import pytest
from conda.base.context import reset_context
from conda.core.prefix_data import PrefixData
from conda.exceptions import CondaError
from conda.testing import CondaCLIFixture, TmpEnvFixture
from conda.testing.integration import package_is_installed
from pytest_mock import MockerFixture

from conda_pypi.python_paths import get_env_python, get_env_stdlib


def test_pip_required_in_target_env(
    tmp_env: TmpEnvFixture, conda_cli: CondaCLIFixture, monkeypatch
):
    monkeypatch.setenv("CONDA_ADD_PIP_AS_PYTHON_DEPENDENCY", "false")
    reset_context()
    with tmp_env("xz") as prefix:
        args = ("pip", "-p", prefix, "--yes", "install", "requests")

        with pytest.raises(CondaError, match="requires python"):
            out, err, rc = conda_cli(*args)
        out, err, rc = conda_cli("install", "-p", prefix, "--yes", "python=3.9")
        PrefixData._cache_.clear()  # clear cache to force re-read of prefix
        assert package_is_installed(str(prefix), "python=3.9")
        assert not package_is_installed(str(prefix), "pip")
        PrefixData._cache_.clear()

        with pytest.raises(CondaError, match="requires pip"):
            out, err, rc = conda_cli(*args)
        out, err, rc = conda_cli("install", "-p", prefix, "--yes", "pip")
        PrefixData._cache_.clear()  # clear cache to force re-read of prefix
        assert package_is_installed(str(prefix), "pip")
        PrefixData._cache_.clear()

        out, err, rc = conda_cli(*args)
        PrefixData._cache_.clear()
        assert rc == 0
        assert package_is_installed(str(prefix), "requests")
    monkeypatch.undo()
    reset_context()


def test_externally_managed(
    tmp_env: TmpEnvFixture, conda_cli: CondaCLIFixture, mocker: MockerFixture
):
    """
    conda-pypi places its own EXTERNALLY-MANAGED file when it is installed in an environment.
    We also need to place it in _new_ environments created by conda.
    """
    base_dir = get_env_stdlib(sys.prefix)
    text = (base_dir / "EXTERNALLY-MANAGED").read_text().strip()
    assert text.startswith("[externally-managed]")
    assert "conda pip" in text

    with tmp_env("python", "pip") as prefix:
        conda_cli("pip", "-p", prefix, "--yes", "install", "requests", "--force-with-pip")
        target_site_packages = get_env_stdlib(prefix)
        externally_managed_file = target_site_packages / "EXTERNALLY-MANAGED"
        text = (externally_managed_file).read_text().strip()
        assert text.startswith("[externally-managed]")
        assert "conda pip" in text
        p = run(
            [get_env_python(prefix), "-m", "pip", "install", "certifi"],
            capture_output=True,
            text=True,
        )
        assert p.returncode != 0
        all_text = p.stderr + p.stdout
        assert "externally-managed-environment" in all_text
        assert "conda pip" in all_text
        assert "--break-system-packages" in all_text
        p = run(
            [get_env_python(prefix), "-m", "pip", "install", "certifi", "--break-system-packages"],
            capture_output=True,
            text=True,
        )
        assert p.returncode == 0
        all_text = p.stderr + p.stdout
        assert (
            "Requirement already satisfied: certifi" in all_text
            or "Successfully installed certifi" in all_text
        )

        # EXTERNALLY-MANAGED is removed when pip is removed
        conda_cli("remove", "-p", prefix, "--yes", "pip")
        assert not externally_managed_file.exists()

        # EXTERNALLY-MANAGED is automatically added when pip is reinstalled by the plugin hook
        conda_cli("install", "-p", prefix, "--yes", "pip")
        assert externally_managed_file.exists()
