"""
Entry point for all conda pypi subcommands

See `conda_pypi.plugin` to see how these are registered with conda
"""

from __future__ import annotations

import argparse
from logging import getLogger

from conda.cli.conda_argparse import (
    add_output_and_prompt_options,
    add_parser_prefix,
)
from conda.exceptions import ArgumentError

from conda_pypi.cli.install import (
    execute as execute_install,
    configure_parser as configure_parser_install,
)
from conda_pypi.cli.convert import (
    execute as execute_convert,
    configure_parser as configure_parser_convert,
)


logger = getLogger(__name__)


def configure_parser(parser: argparse.ArgumentParser):
    """
    Entry point for all argparse configuration
    """

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

    configure_parser_install(sub_parsers)
    configure_parser_convert(sub_parsers)


def execute(args: argparse.Namespace) -> int:
    if args.cmd == "install":
        return execute_install(args)
    elif args.cmd == "convert":
        return execute_convert(args)
    else:
        raise ArgumentError(f"Unknown subcommand: {args.cmd}")
