import pytest
from xprocess import ProcessStarter
from conda.testing.fixtures import conda_cli, path_factory, tmp_env  # noqa: F401


@pytest.fixture(autouse=True)
def do_not_register_envs(monkeypatch):
    """Do not register environments created during tests"""
    monkeypatch.setenv("CONDA_REGISTER_ENVS", "false")


@pytest.fixture(autouse=True)
def do_not_notify_outdated_conda(monkeypatch):
    """Do not notify about outdated conda during tests"""
    monkeypatch.setenv("CONDA_NOTIFY_OUTDATED_CONDA", "false")


@pytest.fixture(scope="session")
def pypi_local_index(xprocess):
    """
    Runs a local PyPI index by serving the folder "tests/pypi_local_index"
    """
    port = "8035"

    class Starter(ProcessStarter):
        pattern = "Serving HTTP"

        args = ["python", "-m", "http.server", "-d", "./tests/pypi_local_index", port]

    # ensure process is running and return its logfile
    xprocess.ensure("pypi_local_index", Starter)

    yield f"http://localhost:{port}"

    xprocess.getinfo("pypi_local_index").terminate()
