"""
conda pypi subcommand for CLI
"""

from __future__ import annotations

import argparse
from pathlib import Path
from logging import getLogger

from conda.auxlib.ish import dals
from conda.cli.conda_argparse import (
    add_output_and_prompt_options,
    add_parser_prefix,
)
from conda.exceptions import ArgumentError
from conda.base.context import context
from conda.models.match_spec import MatchSpec

from conda_pypi import convert_tree


logger = getLogger(__name__)


def configure_parser(parser: argparse.ArgumentParser):
    # This adds --prefix/--name mutually exclusive options
    add_parser_prefix(parser)
    add_output_and_prompt_options(parser)

    sub_parsers = parser.add_subparsers(
        metavar="COMMAND",
        title="commands",
        description="The following subcommands are available.",
        dest="cmd",
        required=True,
    )

    # install subcommand
    summary = "Install PyPI packages as conda packages"
    description = summary
    epilog = dals(
        """

        Install PyPI packages as conda packages.  Any dependencies that are
        available on the configured conda channels will be installed with `conda`,
        while the rest will be converted to conda packages from PyPI.

        Examples:

        Install a single PyPI package into the current conda environment::

            conda pypi install requests

        Install multiple PyPI packages with specific versions::

            conda pypi install "numpy>=1.20" "pandas==1.5.0"

        Install packages into a specific conda environment::

            conda pypi install -n myenv flask django

        Install packages using only PyPI (skip configured conda channels)::

            conda pypi install --override-channels fastapi

        """
    )
    install = sub_parsers.add_parser(
        "install",
        help=summary,
        description=description,
        epilog=epilog,
    )
    install.add_argument(
        "--override-channels",
        action="store_true",
        help="Do not search default or .condarc channels. Will search pypi.",
    )
    install.add_argument(
        "packages",
        metavar="PACKAGE",
        nargs="+",
        help="PyPI packages to install",
    )

    # convert subcommand
    summary = "Build and convert PyPI package or local Python project from wheel to conda package"
    description = summary
    epilog = dals(
        """
        Examples:

        Convert a PyPI package to conda format without installing::

            conda pypi convert requests

        Convert a local Python project to conda package::

            conda pypi convert ./my-python-project

        Convert a package and save to a specific output folder::

            conda pypi convert --output-folder ./conda-packages numpy

        Convert a package from a Git repository::

            conda pypi convert https://github.com/user/repo.git

        """
    )

    convert = sub_parsers.add_parser(
        "convert",
        help=summary,
        description=description,
        epilog=epilog,
    )

    convert.add_argument(
        "--output-folder",
        help="Folder to write output package(s)",
        type=Path,
        required=False,
        default=Path.cwd() / "conda-pypi-output",
    )
    convert.add_argument(
        "project_path",
        metavar="PROJECT",
        help="Convert named path/url as wheel converted to conda.",
    )


def execute(args: argparse.Namespace) -> int:
    if args.cmd == "install":
        return execute_install(args)
    elif args.cmd == "convert":
        return execute_convert(args)
    else:
        raise ArgumentError(f"Unknown subcommand: {args.cmd}")


def execute_install(args: argparse.Namespace) -> int:
    """Execute the install subcommand."""
    prefix_path = Path(context.target_prefix)

    converter = convert_tree.ConvertTree(prefix_path, override_channels=args.override_channels)
    # Convert package strings to MatchSpec objects
    match_specs = [MatchSpec(pkg) for pkg in args.packages]
    converter.convert_tree(match_specs)
    return 0


def execute_convert(args: argparse.Namespace) -> int:
    """Execute the convert subcommand."""
    prefix_path = Path(context.target_prefix)

    package_path = convert_tree.build.pypa_to_conda(
        args.project_path,
        distribution="wheel",
        output_path=args.output_folder,
        prefix=prefix_path,
    )
    print(
        f"Conda package at {package_path} built and converted successfully.  Output folder: {args.output_folder}"
    )
    return 0
