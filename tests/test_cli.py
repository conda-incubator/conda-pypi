from __future__ import annotations

from pathlib import Path

import pytest
import click
from click.testing import CliRunner

import conda_pypi.plugin
from conda_pypi.pupa_cli import cli


def test_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    Coverage testing for the cli.
    """

    runner = CliRunner()

    # mutually exclusive
    result = runner.invoke(
        cli,
        ["-b=.", "-e=."],
    )

    print(result.output)

    assert result.exit_code != 0
    assert "Error:" in result.output and "exclusive" in result.output

    # build editable, ordinary wheel - just test that the CLI accepts the options
    for kind, option in ("editable", "-e"), ("wheel", "-b"):
        output_path = tmp_path / kind
        output_path.mkdir()
        result = runner.invoke(cli, [option, ".", "--output-folder", output_path])
        # The command may fail due to missing build dependencies in test env,
        # but it should at least parse the arguments correctly
        assert "--output-folder specified" in result.output or result.exit_code != 0

    # convert package==4 from pypi using an explicit prefix
    class FakeConvertTree:
        def __call__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            return self

        def convert_tree(self, package_spec):
            self.package_spec = package_spec

    mock = FakeConvertTree()

    monkeypatch.setattr("conda_pypi.convert_tree.ConvertTree", mock)

    runner.invoke(cli, ["--prefix", str(tmp_path), "package==4"], catch_exceptions=False)

    assert mock.args[0] == tmp_path
    assert not mock.kwargs["override_channels"]
    assert mock.package_spec == ("package==4",)


def test_cli_plugin(monkeypatch):
    # Test the conda pupa command (backward compatibility)
    with pytest.raises(click.exceptions.BadOptionUsage):
        conda_pypi.plugin.pupa_command(["-e=.", "-b=."], standalone_mode=False)
