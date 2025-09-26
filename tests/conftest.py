import pytest
import os
import sys
from pathlib import Path

from xprocess import ProcessStarter

pytest_plugins = (
    # Add testing fixtures and internal pytest plugins here
    "conda.testing",
    "conda.testing.fixtures",
)
HERE = Path(__file__).parent


@pytest.fixture(autouse=True)
def do_not_register_envs(monkeypatch):
    """Do not register environments created during tests"""
    monkeypatch.setenv("CONDA_REGISTER_ENVS", "false")


@pytest.fixture(autouse=True)
def do_not_notify_outdated_conda(monkeypatch):
    """Do not notify about outdated conda during tests"""
    monkeypatch.setenv("CONDA_NOTIFY_OUTDATED_CONDA", "false")


@pytest.fixture(scope="session")
def pypi_demo_package_wheel_path() -> Path:
    return HERE / "pypi_local_index" / "demo-package" / "demo_package-0.1.0-py3-none-any.whl"


@pytest.fixture(scope="session")
def pypi_local_index(xprocess):
    """
    Runs a local PyPI index by serving the folder "tests/pypi_local_index"
    """
    port = "8035"

    class Starter(ProcessStarter):
        pattern = "Serving HTTP on"
        timeout = 10
        args = [sys.executable, "-m", "http.server", "-d", HERE / "pypi_local_index", port]
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

    # ensure process is running and return its logfile
    xprocess.ensure("pypi_local_index", Starter)

    yield f"http://localhost:{port}"

    xprocess.getinfo("pypi_local_index").terminate()
