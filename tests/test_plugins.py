from conda.testing.fixtures import CondaCLIFixture, TmpEnvFixture
from pytest_mock import MockerFixture
from conda_pypi.pre_command import extract_whl_or_tarball
from conda_pypi import whl


def test_extract_whl_called(tmp_env: TmpEnvFixture, conda_cli: CondaCLIFixture, mocker: MockerFixture):
    
    spy=mocker.spy(extract_whl_or_tarball.extract_whl, "extract_whl_as_conda_pkg")
    with tmp_env() as prefix:
        try:
            conda_cli("install", "boltons-25.0.0-py3-none-any.whl",  "-p", prefix)
        except:
            pass

    spy.assert_called_once() 


def test_plugin_invoked(tmp_env: TmpEnvFixture, conda_cli: CondaCLIFixture, mocker: MockerFixture):
    spy=mocker.spy(whl, "add_whl_support")
    with tmp_env() as prefix:
        try:
            conda_cli("install", "boltons-25.0.0-py3-none-any.whl",  "-p", prefix)
        except:
            pass

    spy.assert_called_once()  
