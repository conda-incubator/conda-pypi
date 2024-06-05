from conda import plugins

from . import cli
from .main import ensure_target_env_has_externally_managed


@plugins.hookimpl
def conda_subcommands():
    yield plugins.CondaSubcommand(
        name="pip",
        summary="Run pip commands within conda environments in a safer way",
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
    yield plugins.CondaPostCommand(
        name="conda-pypi-post-list",
        action=cli.list.post_command,
        run_for={"list"},
    )
    yield plugins.CondaPostCommand(
        name="conda-pypi-post-install-create",
        action=cli.install.post_command,
        run_for={"install", "create"},
    )
