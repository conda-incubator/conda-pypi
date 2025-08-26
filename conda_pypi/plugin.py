from conda import plugins

from conda_pypi import cli
from conda_pypi.main import ensure_target_env_has_externally_managed


def pupa_command(
    args, standalone_mode=True
):  # standalone_mode=False avoids click SystemExit(); for testing.
    """Backward compatibility command for conda-pupa users."""
    from conda_pypi import pupa_cli

    return pupa_cli.cli(prog_name="conda pupa", args=args, standalone_mode=standalone_mode)


@plugins.hookimpl
def conda_subcommands():
    yield plugins.CondaSubcommand(
        name="pip",
        summary="Run pip commands within conda environments in a safer way",
        action=cli.pip.execute,
        configure_parser=cli.pip.configure_parser,
    )
    # Backward compatibility subcommand
    yield plugins.CondaSubcommand(
        name="pupa",
        action=pupa_command,
        summary="Update package index metadata files (conda-pupa compatibility)",
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
