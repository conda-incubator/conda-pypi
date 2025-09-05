from conda import plugins

from conda_pypi import cli
from conda_pypi.main import ensure_target_env_has_externally_managed


@plugins.hookimpl
def conda_subcommands():
    yield plugins.CondaSubcommand(
        name="pip",
        summary="Run pip commands within conda environments in a safer way",
        action=cli.pip.execute,
        configure_parser=cli.pip.configure_parser,
    )
    yield plugins.CondaSubcommand(
        name="pypi",
        action=cli.pypi.execute,
        configure_parser=cli.pypi.configure_parser,
        summary="Install PyPI packages as conda packages",
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
