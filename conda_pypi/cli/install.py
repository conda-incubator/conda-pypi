from argparse import _SubParsersAction, Namespace
from pathlib import Path

from conda.auxlib.ish import dals
from conda.base.context import context
from conda.models.match_spec import MatchSpec

from conda_pypi import convert_tree
from conda_pypi.downloader import get_package_finder


def configure_parser(parser: _SubParsersAction) -> None:
    """
    Configure all subcommand arguments and options via argparse
    """
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

        Install packages from an alternative package index URL::

            conda pypi install --index-url https://example.com/simple fastapi

        """
    )
    install = parser.add_parser(
        "install",
        help=summary,
        description=description,
        epilog=epilog,
    )
    install.add_argument(
        "--override-channels",
        action="store_true",
        help="Do not search default or .condarc channels. Will search PyPI.",
    )
    install.add_argument(
        "-i",
        "--index-url",
        dest="index_urls",
        action="append",
        help="Add a PyPI index URL (can be used multiple times).",
    )
    install.add_argument(
        "packages",
        metavar="PACKAGE",
        nargs="+",
        help="PyPI packages to install",
    )


def execute(args: Namespace) -> int:
    """
    Entry point for the `conda pypi install` subcommand.
    """
    prefix_path = Path(context.target_prefix)

    if args.index_urls:
        index_urls = tuple(dict.fromkeys(args.index_urls))
        finder = get_package_finder(prefix_path, index_urls)
    else:
        finder = None

    converter = convert_tree.ConvertTree(
        prefix_path,
        override_channels=args.override_channels,
        finder=finder,
    )

    # Convert package strings to MatchSpec objects
    match_specs = [MatchSpec(pkg) for pkg in args.packages]
    converter.convert_tree(match_specs)

    return 0
