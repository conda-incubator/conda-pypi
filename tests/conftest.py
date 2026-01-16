import pytest
from pathlib import Path
from . import http_test_server


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
def pypi_local_index():
    """
    Runs a local PyPI index by serving the folder "tests/pypi_local_index"
    """
    base = HERE / "pypi_local_index"
    http = http_test_server.run_test_server(str(base))

    http_sock_name = http.socket.getsockname()
    yield f"http://{http_sock_name[0]}:{http_sock_name[1]}"

    http.shutdown()


@pytest.fixture(scope="session")
def conda_local_channel():
    """
    Runs a local conda channel by serving the folder "tests/conda_local_channel"
    This provides a mock conda channel with pre-converted packages for testing
    dependency resolution without requiring network access.
    """
    base = HERE / "conda_local_channel"
    http = http_test_server.run_test_server(str(base))

    http_sock_name = http.socket.getsockname()
    yield f"http://{http_sock_name[0]}:{http_sock_name[1]}"

    http.shutdown()

