"""
Command line interface for conda-pupa.
"""

from pathlib import Path

import click

import conda_pupa.build
import conda_pupa.convert_tree


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "-c",
    "--channel",
    help="Additional channel to search for packages.",
    multiple=True,
)
@click.option(
    "-O",
    "--override-channels/--no-override-channels",
    help="Do not search default or .condarc channels. Will search pypi.",
    default=False,
    show_default=True,
)
@click.option(
    "-e",
    "--editable",
    required=False,
    help="Build named path as editable package; install to link checkout to environment.",
)
@click.option(
    "-b",
    "--build",
    required=False,
    help="Build named path as wheel converted to conda.",
)
@click.option(
    "-p",
    "--prefix",
    help="Full path to environment location (i.e. prefix).",
    required=False,
)
# keep or change conda-build's argument naming?
@click.option(
    "--output-folder", help="Folder to write output package(s)", required=False
)
@click.argument(
    "package_spec",
    nargs=-1,
)
@click.option("-n", "--name", help="Name of environment.", required=False)
def cli(
    channel,
    editable,
    build,
    prefix,
    name,
    override_channels,
    package_spec,
    output_folder,
):
    if editable and build:
        raise click.BadOptionUsage("build", "build and editable are mutually exclusive")

    if output_folder:
        output_folder = Path(output_folder)

    if editable:
        print(
            "Editable at ",
            conda_pupa.build.pypa_to_conda(
                editable, distribution="editable", output_path=output_folder
            ),
        )

    elif build:
        print(
            "Conda package at ",
            conda_pupa.build.pypa_to_conda(
                build, distribution="wheel", output_path=output_folder
            ),
        )

    else:
        if prefix:
            prefix = Path(prefix).expanduser()
        # XXX or environment name plus default prefix

        converter = conda_pupa.convert_tree.ConvertTree(
            prefix, override_channels=override_channels
        )
        converter.convert_tree(package_spec)
