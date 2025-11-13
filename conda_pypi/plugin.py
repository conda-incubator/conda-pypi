from __future__ import annotations

from conda.plugins import hookimpl
from conda.plugins.types import CondaSubcommand, CondaPostCommand

from conda_pypi import cli
from conda_pypi import post_command
from conda_pypi.main import ensure_target_env_has_externally_managed
from conda_pypi.whl import add_whl_support


@hookimpl
def conda_subcommands():
    yield CondaSubcommand(
        name="pypi",
        action=cli.main.execute,
        configure_parser=cli.main.configure_parser,
        summary="Install PyPI packages as conda packages",
    )


@hookimpl
def conda_post_commands():
    yield CondaPostCommand(
        name="conda-pypi-ensure-target-env-has-externally-managed",
        action=ensure_target_env_has_externally_managed,
        run_for={"install", "create", "update", "remove"},
    )
    yield CondaPostCommand(
        name="conda-pypi-post-install-create",
        action=post_command.install.post_command,
        run_for={"install", "create"},
    )


# @hookimpl
# def conda_pre_commands() -> Generator[plugins.CondaPreCommand, None, None]:
#     yield CondaPreCommand(
#         name="conda-whl-support",
#         action=lambda _ : add_whl_support(),
#         run_for={
#             "create",
#             "install",
#             "remove",
#             "rename",
#             "update",
#             "env_create",
#             "env_update",
#             "list",
#         },
#     )

# Commenting out the plugin implementation and directly calling `add_whl_support`.
add_whl_support()
