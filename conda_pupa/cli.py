"""
Command line interface for conda-pupa.
"""

import contextlib
import tempfile
from pathlib import Path

import click
import conda.base.context

import conda_pupa.build
import conda_pupa.convert_tree
import conda_pupa.installer


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
    help="Build and install named path as editable package, linking project into environment.",
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

    if prefix:
        prefix = Path(prefix).expanduser()
    else:
        prefix = Path(conda.base.context.context.target_prefix)

    if editable:
        if output_folder:
            print(
                "--output-folder specified; saving editable .conda instead of install."
            )
            output_path_manager = contextlib.nullcontext(output_folder)
        else:
            output_path_manager = tempfile.TemporaryDirectory("pupa")
        with output_path_manager as output_path:
            package = conda_pupa.build.pypa_to_conda(
                editable,
                distribution="editable",
                output_path=Path(output_path),
                prefix=prefix,
            )
            if not output_folder:
                conda_pupa.installer.install_ephemeral_conda(prefix, package)

    elif build:
        print(
            "Conda package at ",
            conda_pupa.build.pypa_to_conda(
                build, distribution="wheel", output_path=output_folder, prefix=prefix
            ),
        )

    else:
        converter = conda_pupa.convert_tree.ConvertTree(
            prefix, override_channels=override_channels
        )
        converter.convert_tree(package_spec)
