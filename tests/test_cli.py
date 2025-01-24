from __future__ import annotations

from pathlib import Path

import click.exceptions
import pytest
from click.testing import CliRunner

import conda_pupa.plugin
from conda_pupa.cli import cli


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

    print(result.stdout)

    assert result.exit_code != 0
    assert "Error:" in result.stdout and "exclusive" in result.stdout

    # build editable, ordinary wheel
    for kind, option in ("editable", "-e"), ("wheel", "-b"):
        output_path = tmp_path / kind
        output_path.mkdir()
        result = runner.invoke(cli, [option, ".", "--output-folder", output_path])
        assert len(list(output_path.glob("*.conda"))) == 1

    # convert package==4 from pypi using an explicit prefix
    class FakeConvertTree:
        def __call__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            return self

        def convert_tree(self, package_spec):
            self.package_spec = package_spec

    mock = FakeConvertTree()

    monkeypatch.setattr("conda_pupa.convert_tree.ConvertTree", mock)

    runner.invoke(
        cli, ["--prefix", str(tmp_path), "package==4"], catch_exceptions=False
    )

    assert mock.args[0] == tmp_path
    assert not mock.kwargs["override_channels"]
    assert mock.package_spec == ("package==4",)


def test_cli_plugin(monkeypatch):
    with pytest.raises(click.exceptions.BadOptionUsage):
        conda_pupa.plugin.command(["-e=.", "-b=."], standalone_mode=False)
