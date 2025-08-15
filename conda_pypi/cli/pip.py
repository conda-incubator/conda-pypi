"""
conda pip subcommand for CLI - now powered by conda-pupa
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import contextlib
from logging import getLogger
from pathlib import Path

from conda.cli.common import confirm_yn
from conda.cli.conda_argparse import (
    add_output_and_prompt_options,
    add_parser_help,
    add_parser_prefix,
)
from conda.exceptions import ArgumentError
import conda.base.context

logger = getLogger(f"conda.{__name__}")


def configure_parser(parser: argparse.ArgumentParser):
    add_parser_help(parser)
    add_parser_prefix(parser)
    add_output_and_prompt_options(parser)

    subparser = parser.add_subparsers(dest="subcmd", required=True)

    install = subparser.add_parser(
        "install",
        help="Install a PyPI package, archive or URL, "
        "converting to conda packages when possible.",
    )
    install.add_argument(
        "-U",
        "--upgrade",
        action="store_true",
        help="Tell pip to upgrade the package if it's already installed.",
    )
    install.add_argument(
        "--force-reinstall",
        action="store_true",
        help="Reinstall all packages even if they are already installed.",
    )
    install.add_argument(
        "--override-channels",
        action="store_true",
        help="Do not search default or .condarc channels. Will search pypi.",
    )
    install.add_argument(
        "-c",
        "--channel",
        metavar="CHANNEL",
        action="append",
        help="Additional channel to search for packages.",
    )
    install.add_argument(
        "-e", "--editable",
        metavar="<path/url>",
        help="Install a project in editable mode (i.e. setuptools 'develop mode') "
        "from a local project path or a VCS url."
    )
    install.add_argument("packages", metavar="package", nargs="*")


def execute(args: argparse.Namespace) -> int:
    if not args.packages and not args.editable:
        raise ArgumentError(
            "No packages requested. Please provide one or more packages, "
            "or one editable specification."
        )

    from conda.common.io import Spinner
    from ..utils import get_prefix
    from ..main import ensure_externally_managed
    from ..convert_tree import ConvertTree
    from ..build import pypa_to_conda
    from ..installer import install_ephemeral_conda

    prefix = get_prefix(args.prefix, args.name)
    
    if not args.quiet:
        print(f"Using conda-pupa backend for PyPI package conversion")
        print(f"Target environment: {prefix}")

    # Handle editable installs
    if args.editable:
        if not args.quiet:
            print(f"Installing editable package: {args.editable}")
        
        with tempfile.TemporaryDirectory("pupa") as output_path:
            package = pypa_to_conda(
                args.editable,
                distribution="editable",
                output_path=Path(output_path),
                prefix=prefix,
            )
            install_ephemeral_conda(prefix, package)
        
        if os.environ.get("CONDA_BUILD_STATE") != "BUILD":
            ensure_externally_managed(prefix)
        return 0

    # Handle regular package installs using conda-pupa's ConvertTree
    if args.packages:
        if not args.quiet:
            print(f"Converting and installing packages: {', '.join(args.packages)}")
        
        with Spinner("Converting PyPI packages to conda format", enabled=not args.quiet, json=args.json):
            converter = ConvertTree(
                prefix, 
                override_channels=args.override_channels
            )
            converter.convert_tree(args.packages)
        
        if not args.quiet:
            print("Package conversion and installation completed")
        
        if os.environ.get("CONDA_BUILD_STATE") != "BUILD":
            ensure_externally_managed(prefix)
        return 0

    return 0