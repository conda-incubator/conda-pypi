"""
Command line interface for conda-pypi.

This module provides the main CLI commands for converting and installing
PyPI packages using conda-pypi.
"""

from __future__ import annotations

import argparse
import traceback
from contextlib import nullcontext
from logging import getLogger
from pathlib import Path

from conda.cli.conda_argparse import (
    add_output_and_prompt_options,
    add_parser_help,
    add_parser_prefix,
)
from conda.exceptions import ArgumentError
from conda.reporters import get_spinner

from .core import convert_packages, install_packages, prepare_packages_for_installation
from .main import validate_target_env
from .utils import ensure_externally_managed
from .utils import get_prefix, get_package_finder
from .auth import ANACONDA_AUTH_AVAILABLE, get_auth_install_message


logger = getLogger(f"conda.{__name__}")


def configure_parser(parser: argparse.ArgumentParser):
    """Configure the argument parser for conda pypi subcommand."""
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
        action="store_true",
        help="Install packages in editable mode (development mode).",
    )
    install.add_argument(
        "--index",
        dest="index_urls",
        action="append",
        help="Add a PyPI index URL (can be used multiple times). "
        "Authentication via anaconda-auth is supported for private indexes (optional dependency).",
    )
    install.add_argument("packages", metavar="package", nargs="*")

    convert.add_argument(
        "--override-channels",
        action="store_true",
        help="Do not search default or .condarc channels. Will search pypi.",
    )
    convert.add_argument(
        "-d",
        "--dest",
        "-o",
        "--output-dir",
        dest="output_dir",
        type=Path,
        help="Directory to save converted .conda packages (default: current directory)",
    )
    convert.add_argument(
        "--index",
        dest="index_urls",
        action="append",
        help="Add a PyPI index URL (can be used multiple times). "
        "Authentication via anaconda-auth is supported for private indexes (optional dependency).",
    )
    convert.add_argument("packages", metavar="package", nargs="*")


def execute(args: argparse.Namespace) -> int:
    """Execute the conda pypi subcommand."""
    if args.subcmd == "install":
        return execute_install(args)
    elif args.subcmd == "convert":
        return execute_convert(args)
    else:
        logger.error(f"Unknown subcommand: {args.subcmd}")
        return 1


def execute_install(args: argparse.Namespace) -> int:
    """Execute the install subcommand."""
    if not args.packages:
        raise ArgumentError(
            "No packages requested. Please provide one or more packages, "
            "or one editable specification."
        )

    prefix = get_prefix(args.prefix, args.name)

    if not args.quiet:
        logger.info("Using conda-pypi backend for PyPI package conversion")

    packages_to_process = validate_target_env(prefix, args.packages)
    if not packages_to_process:
        if not args.quiet:
            print("All packages are already installed.")
        return 0

    ensure_externally_managed(prefix)

    if args.dry_run:
        if not args.quiet:
            print(f"Would install packages: {', '.join(packages_to_process)}")
        return 0

    try:
        if not args.quiet:
            action = "Installing" if args.editable else "Converting and installing"
            logger.info(f"{action} packages: {', '.join(args.packages)}")

        finder = None
        if args.index_urls:
            if not args.quiet:
                if len(args.index_urls) == 1:
                    print(f"Using custom PyPI index: {args.index_urls[0]}")
                else:
                    print(f"Using custom PyPI indexes: {', '.join(args.index_urls)}")

                if ANACONDA_AUTH_AVAILABLE:
                    print("Authentication via anaconda-auth is available")
                else:
                    print(f"Note: {get_auth_install_message()}")

            finder = get_package_finder(prefix, args.index_urls)

        spinner_message = (
            "Installing packages" if args.editable else "Converting PyPI packages to conda format"
        )

        spinner_context = get_spinner(spinner_message) if not args.quiet else nullcontext()
        with spinner_context:
            cached_package_names = prepare_packages_for_installation(
                args.packages,
                prefix,
                override_channels=args.override_channels,
                editable=args.editable,
                with_dependencies=not args.editable,
                finder=finder,
            )

        # Install conda packages (if any were converted)
        if cached_package_names:
            if not args.quiet:
                with get_spinner("Installing converted packages"):
                    install_packages(cached_package_names, prefix, args.override_channels)
            else:
                install_packages(cached_package_names, prefix, args.override_channels)

        # Provide appropriate completion message
        if cached_package_names or args.editable:
            if not args.quiet:
                logger.info("Installation completed")
        else:
            if not args.quiet:
                logger.warning("No packages were successfully converted")
            return 1

    except Exception as e:
        logger.error(f"Installation failed: {e}")
        if getattr(args, "verbose", False):
            traceback.print_exc()
        return 1

    return 0


def execute_convert(args: argparse.Namespace) -> int:
    """Execute the convert subcommand."""
    if not args.packages:
        raise ArgumentError("No packages requested. Please provide one or more packages.")

    prefix = get_prefix(args.prefix, args.name)

    output_dir = args.output_dir or Path.cwd()
    output_dir = output_dir.resolve()

    if not args.quiet:
        logger.info(f"Converting packages: {', '.join(args.packages)}")

    finder = None
    if args.index_urls:
        if not args.quiet:
            if len(args.index_urls) == 1:
                print(f"Using custom PyPI index: {args.index_urls[0]}")
            else:
                print(f"Using custom PyPI indexes: {', '.join(args.index_urls)}")

            try:
                if ANACONDA_AUTH_AVAILABLE:
                    print("Authentication via anaconda-auth is available")
                else:
                    print(f"Note: {get_auth_install_message()}")
            except ImportError:
                pass

        finder = get_package_finder(prefix, args.index_urls)

    if not args.quiet:
        with get_spinner("Converting PyPI packages to .conda format"):
            converted_packages = convert_packages(
                args.packages,
                prefix,
                output_dir,
                override_channels=args.override_channels,
                finder=finder,
            )
    else:
        converted_packages = convert_packages(
            args.packages,
            prefix,
            output_dir,
            override_channels=args.override_channels,
            finder=finder,
        )

    if not args.quiet:
        if converted_packages:
            logger.info(f"Successfully converted {len(converted_packages)} packages:")
            for pkg in converted_packages:
                logger.info(f"  - {pkg.name}")
            logger.info(f"Packages saved to: {output_dir}")
        else:
            logger.warning("No packages were successfully converted")

    return 0 if converted_packages else 1
