"""
conda pypi subcommand for CLI
"""

from __future__ import annotations

import argparse
from pathlib import Path
from logging import getLogger

from conda.cli.conda_argparse import (
    add_output_and_prompt_options,
    add_parser_help,
    add_parser_prefix,
)
from conda.exceptions import ArgumentError
from conda.base.context import context

logger = getLogger(__name__)


def configure_parser(parser: argparse.ArgumentParser):
    add_parser_help(parser)
    # This adds --prefix/--name mutually exclusive options
    add_parser_prefix(parser)
    add_output_and_prompt_options(parser)

    sub_parsers = parser.add_subparsers(
        metavar="COMMAND",
        title="commands",
        description="The following subcommands are available.",
        dest="cmd",
        action=_GreedySubParsersAction,
        required=True,
    )

    # install subcommand
    install = subparser.add_parser(
        "install",
        help="Install PyPI packages as conda packages",
    )
    install.add_argument(
        "--override-channels",
        action="store_true",
        help="Do not search default or .condarc channels. Will search pypi.",
    )
    install.add_argument(
        "packages",
        metavar="PACKAGE",
        nargs="*",
        help="PyPI packages to install",
    )

    # convert subcommand
    convert = subparser.add_parser(
        "convert",
        help="Build/convert Python packages to conda packages without installation",
    )
    # TODO: add --name option with mutually exclusive with --prefix
    convert.add_argument(
        "-p",
        "--prefix",
        metavar="<path>",
        help="Target prefix for installation",
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
    if args.subcmd == "install":
        return execute_install(args)
    elif args.subcmd == "convert":
        return execute_convert(args)
    else:
        raise ArgumentError(f"Unknown subcommand: {args.subcmd}")


def execute_install(args: argparse.Namespace) -> int:
    """Execute the install subcommand."""
    from conda_pypi import convert_tree

    # Handle package installation from PyPI
    from conda.models.match_spec import MatchSpec

    if args.prefix:
        prefix_path = Path(args.prefix).expanduser()
    else:
        prefix_path = Path(context.target_prefix)

    converter = convert_tree.ConvertTree(prefix_path, override_channels=args.override_channels)
    # Convert package strings to MatchSpec objects
    match_specs = [MatchSpec(pkg) for pkg in args.packages]
    converter.convert_tree(match_specs)
    return 0


def execute_convert(args: argparse.Namespace) -> int:
    """Execute the convert subcommand."""
    from conda_pypi import convert_tree

    if args.prefix:
        prefix_path = Path(args.prefix).expanduser()
    else:
        prefix_path = Path(context.target_prefix)

    package_path = convert_tree.build.pypa_to_conda(
        args.project_path, distribution="wheel", output_path=args.output_folder, prefix=prefix_path
    )
    print(
        f"Conda package at {package_path} built and converted successfully.  Output folder: {args.output_folder}"
    )
    return 0


"""
def execute_develop(args: argparse.Namespace) -> int:
    # Handle editable installation
    if args.output_folder:
        print("--output-folder specified; saving editable .conda instead of install.")
        output_path_manager = contextlib.nullcontext(args.output_folder)
    else:
        output_path_manager = tempfile.TemporaryDirectory("conda-pypi")

    with output_path_manager as output_path:
        package = convert_tree.build.pypa_to_conda(
            args.editable,
            distribution="editable",
            output_path=Path(output_path),
            prefix=get_prefix(args.prefix, args.name),
        )
        if not args.output_folder:
            installer.install_ephemeral_conda(get_prefix(args.prefix, args.name), package)
    return 0
"""
