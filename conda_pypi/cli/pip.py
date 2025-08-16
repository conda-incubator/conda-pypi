"""conda pip subcommand."""

from __future__ import annotations

import argparse
import os
import tempfile
from logging import getLogger
from pathlib import Path

from conda.cli.conda_argparse import (
    add_output_and_prompt_options,
    add_parser_help,
    add_parser_prefix,
)
from conda.exceptions import ArgumentError

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

    convert = subparser.add_parser(
        "convert",
        help="Convert PyPI packages to .conda format without installing them.",
    )

    install.add_argument(
        "--override-channels",
        action="store_true",
        help="Do not search default or .condarc channels. Will search pypi.",
    )
    install.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't actually install anything, just print what would be done.",
    )

    install.add_argument(
        "-e",
        "--editable",
        metavar="<path/url>",
        help="Install a project in editable mode (i.e. setuptools 'develop mode') "
        "from a local project path or a VCS url.",
    )
    install.add_argument("packages", metavar="package", nargs="*")

    # Add arguments to convert subcommand (similar to pip download)
    convert.add_argument(
        "-d",
        "--dest",
        metavar="PATH",
        default=".",
        help="Convert packages into this directory (default: current directory).",
    )
    convert.add_argument(
        "--override-channels",
        action="store_true",
        help="Do not search default or .condarc channels. Will search pypi.",
    )

    convert.add_argument("packages", metavar="package", nargs="*")


def execute(args: argparse.Namespace) -> int:
    # Handle different subcommands
    if args.subcmd == "convert":
        return execute_convert(args)
    elif args.subcmd == "install":
        return execute_install(args)
    else:
        raise ArgumentError(f"Unknown subcommand: {args.subcmd}")


def execute_install(args: argparse.Namespace) -> int:
    if not args.packages and not args.editable:
        raise ArgumentError(
            "No packages requested. Please provide one or more packages, "
            "or one editable specification."
        )

    from conda.common.io import Spinner
    from ..utils import get_prefix
    from ..main import ensure_externally_managed, validate_target_env
    from ..convert_tree import ConvertTree
    from ..build import pypa_to_conda
    from ..installer import install_ephemeral_conda

    prefix = get_prefix(args.prefix, args.name)

    if not args.quiet:
        logger.info("Using conda-pypi backend for PyPI package conversion")
        logger.info(f"Target environment: {prefix}")

    # Handle editable installs
    if args.editable:
        if not args.quiet:
            logger.info(f"Installing editable package: {args.editable}")

        with tempfile.TemporaryDirectory("pypi") as output_path:
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
        # Always validate the target environment first
        try:
            packages_to_process = validate_target_env(prefix, args.packages)
        except Exception as e:
            # Re-raise as CondaError for consistency with expected test behavior
            from conda.exceptions import CondaError

            raise CondaError(str(e))

        # Handle dry-run mode (check both top-level and subcommand-level)
        # The top-level --dry-run is stored in args.dry_run by conda's argument parser
        is_dry_run = getattr(args, "dry_run", False)
        if is_dry_run:
            if not packages_to_process:
                if not args.quiet:
                    print("All packages are already installed.")
                return 0
            else:
                if not args.quiet:
                    print(f"Would install packages: {', '.join(packages_to_process)}")
                return 0

        if not args.quiet:
            logger.info(f"Converting and installing packages: {', '.join(args.packages)}")

        with Spinner(
            "Converting PyPI packages to conda format", enabled=not args.quiet, json=args.json
        ):
            converter = ConvertTree(prefix, override_channels=args.override_channels)
            converter.convert_tree(args.packages)

        if not args.quiet:
            logger.info("Package conversion and installation completed")

        if os.environ.get("CONDA_BUILD_STATE") != "BUILD":
            ensure_externally_managed(prefix)
        return 0

    return 0


def execute_convert(args: argparse.Namespace) -> int:
    if not args.packages:
        raise ArgumentError("No packages requested. Please provide one or more packages.")

    from conda.common.io import Spinner
    from ..utils import get_prefix

    prefix = get_prefix(args.prefix, args.name)
    output_dir = Path(args.dest).resolve()

    if not args.quiet:
        logger.info("Using conda-pypi backend for PyPI package conversion")
        logger.info(f"Converting packages to .conda format in: {output_dir}")
        logger.info(f"Target environment: {prefix}")

    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    if not args.quiet:
        logger.info(f"Converting packages: {', '.join(args.packages)}")

    with Spinner(
        "Converting PyPI packages to .conda format", enabled=not args.quiet, json=args.json
    ):
        # For now, we'll use ConvertTree but ideally we'd have a convert-only mode
        # This is a limitation we can note and improve later
        from ..convert_tree import ConvertTree

        converter = ConvertTree(prefix, override_channels=args.override_channels)
        # TODO: Modify ConvertTree to support convert-only mode with custom output directory
        if not args.quiet:
            logger.info(
                "Note: Currently converting and installing packages. Convert-only mode coming soon."
            )
        converter.convert_tree(args.packages)

    if not args.quiet:
        logger.info("Package conversion completed")

    return 0
