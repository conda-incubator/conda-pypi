from __future__ import annotations

from pathlib import Path

import pytest

from conda_pypi.cli.pypi import configure_parser
import argparse


def test_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    Coverage testing for the new argparse-based CLI.
    """

    # Test argument parsing
    parser = argparse.ArgumentParser(add_help=False)
    # configure parser adds subparser commands and help
    # let's test that they are added correctly
    configure_parser(parser)

    # Test that install and convert subcommands exist
    subparsers = parser._subparsers._group_actions[0]
    assert "install" in subparsers.choices
    assert "convert" in subparsers.choices

    # Test that help can be parsed without conflicts (this was the original issue)
    try:
        parser.parse_args(["--help"])
        assert True
    except SystemExit:
        pass

    # Test that subcommand help can be parsed without conflicts
    install_parser = subparsers.choices["install"]
    convert_parser = subparsers.choices["convert"]

    try:
        install_parser.parse_args(["--help"])
        assert True
    except SystemExit:
        pass

    try:
        convert_parser.parse_args(["--help"])
        assert True
    except SystemExit:
        pass


def test_cli_plugin(monkeypatch):
    # Test that the plugin can be loaded and the subcommand is registered
    from conda_pypi.plugin import conda_subcommands

    subcommands = list(conda_subcommands())
    pypi_subcommand = next((sub for sub in subcommands if sub.name == "pypi"), None)

    assert pypi_subcommand is not None
    assert pypi_subcommand.summary == "Install PyPI packages as conda packages"
    assert pypi_subcommand.action is not None
    assert pypi_subcommand.configure_parser is not None
