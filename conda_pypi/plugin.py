from conda import plugins

from . import cli
from .main import ensure_target_env_has_externally_managed


@plugins.hookimpl
def conda_subcommands():
    yield plugins.CondaSubcommand(
        name="pip",
        summary="Install PyPI packages by converting them to .conda format",
        action=cli.pip.execute,
        configure_parser=cli.pip.configure_parser,
    )


@plugins.hookimpl
def conda_post_commands():
    yield plugins.CondaPostCommand(
        name="conda-pypi-ensure-target-env-has-externally-managed",
        action=ensure_target_env_has_externally_managed,
        run_for={"install", "create", "update", "remove"},
    )
