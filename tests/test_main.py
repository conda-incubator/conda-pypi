import sys

from conda_pypi.main import run_conda_cli, run_conda_install


def test_run_conda_cli(mocker):
    mock = mocker.patch("conda_pypi.main.run_module")
    
    old_sys_argv = sys.argv
    run_conda_cli()

    # Ensure conda module is called
    mock.assert_called_once_with("conda", run_name="__main__")

    # Ensure args are restored
    assert sys.argv == old_sys_argv
    

def test_run_conda_install_basic(mocker):
    mock = mocker.patch("conda_pypi.main.run_conda_cli")
    
    run_conda_install(
        prefix="idontexist",
        specs=["numpy",]
    )

    # Ensure conda module is called
    mock.assert_called_once_with("install", "--prefix", "idontexist", "numpy")


def test_run_conda_install(mocker):
    mock = mocker.patch("conda_pypi.main.run_conda_cli")
    
    run_conda_install(
        prefix="idontexist",
        specs=["numpy","scipy"],
        dry_run=True,
        quiet=True,
        verbosity=2,
        force_reinstall=True,
        yes=True,
        json=True,
        channels=["mychannel", "abc"],
        override_channels=True,
    )

    # Ensure conda module is called
    mock.assert_called_once_with(
        "install", "--prefix", "idontexist", "--dry-run", "--quiet", "-vv", "--force-reinstall", "--yes", "--json", "--channel", "mychannel", "--channel" , "abc", "--override-channels", "numpy", "scipy"
    )