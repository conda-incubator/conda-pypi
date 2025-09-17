"""
Tests that use run `conda pypi install` use `conda_cli` as the primary caller
"""

from __future__ import annotations


def test_cli(conda_cli):
    """
    Test that pypi subcommands exist by checking their help output.
    """
    # Test that install subcommand exists and help works
    # Help commands raise SystemExit, so we need to handle that
    out, err, rc = conda_cli("pypi", "install", "--help", raises=SystemExit)
    assert rc.value.code == 0  # SystemExit(0) means success
    assert "PyPI packages to install" in out

    # Test that convert subcommand exists and help works
    out, err, rc = conda_cli("pypi", "convert", "--help", raises=SystemExit)
    assert rc.value.code == 0
    assert "Convert named path/url as wheel converted to conda" in out


def test_cli_plugin(monkeypatch):
    # Test that the plugin can be loaded and the subcommand is registered
    from conda_pypi.plugin import conda_subcommands

    subcommands = list(conda_subcommands())
    pypi_subcommand = next((sub for sub in subcommands if sub.name == "pypi"), None)

    assert pypi_subcommand is not None
    assert pypi_subcommand.summary == "Install PyPI packages as conda packages"
    assert pypi_subcommand.action is not None
    assert pypi_subcommand.configure_parser is not None


def test_install_wheel(conda_cli, tmp_env, pypi_local_index):
    """
    Runs a basic test that installs a wheel into a conda environment by first converting it
    to a conda package.
    """
    with tmp_env("python", "pip"):
        out, err, rc = conda_cli("pypi", "install", "--index", pypi_local_index, "demo-package")
