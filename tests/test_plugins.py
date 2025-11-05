from conda.testing.fixtures import CondaCLIFixture, TmpEnvFixture
from pytest_mock import MockerFixture
from conda_pypi.pre_command import extract_whl_or_tarball
from conda_pypi.pre_command.extract_whl import extract_whl_as_conda_pkg
from conda_pypi import plugin

from pathlib import Path

WHL_URL= "https://files.pythonhosted.org/packages/45/7f/0e961cf3908bc4c1c3e027de2794f867c6c89fb4916fc7dba295a0e80a2d/boltons-25.0.0-py3-none-any.whl"

def test_extract_whl_as_conda_called(tmp_env: TmpEnvFixture, conda_cli: CondaCLIFixture, mocker: MockerFixture, pypi_demo_package_wheel_path: Path, tmp_pkgs_dir: Path):
    with tmp_env("python") as prefix:
        spy=mocker.spy(extract_whl_or_tarball.extract_whl, "extract_whl_as_conda_pkg")
        conda_cli("install", pypi_demo_package_wheel_path,  "-p", prefix)
        spy.assert_called_once() 


def test_plugin_invoked(tmp_env: TmpEnvFixture, conda_cli: CondaCLIFixture, mocker: MockerFixture, pypi_demo_package_wheel_path: Path):
    with tmp_env("python") as prefix:
        spy=mocker.spy(plugin, "add_whl_support")
        conda_cli("install", pypi_demo_package_wheel_path,  "-p", prefix)
        spy.assert_called_once()  


def test_extract_whl_as_conda_pkg(tmp_env: TmpEnvFixture, conda_cli: CondaCLIFixture, mocker: MockerFixture, pypi_demo_package_wheel_path: Path
):
    with tmp_env("python") as prefix:
        extract_whl_as_conda_pkg(pypi_demo_package_wheel_path, prefix)

