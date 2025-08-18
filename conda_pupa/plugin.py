"""
Conda command plugin, provide "conda pupa"
"""

import conda.plugins


def command(
    args, standalone_mode=True
):  # standalone_mode=False avoids click SystemExit(); for testing.
    import conda_pupa.cli

    return conda_pupa.cli.cli(prog_name="conda pupa", args=args, standalone_mode=standalone_mode)


@conda.plugins.hookimpl
def conda_subcommands():
    yield conda.plugins.CondaSubcommand(
        name="pupa", action=command, summary="Update package index metadata files."
    )
