from argparse import _SubParsersAction, Namespace
from pathlib import Path

from conda.auxlib.ish import dals
from conda.base.context import context
from conda.models.match_spec import MatchSpec

from conda_pypi import convert_tree
from conda_pypi.constants import DEFAULT_PYPI_INDEX_URL
from conda_pypi.main import run_conda_install


def configure_parser(parser: _SubParsersAction) -> None:
    """
    Configure all subcommand arguments and options via argparse
    """
    summary = "Install PyPI packages as conda packages"
    description = summary
    epilog = dals(
        """

        Install PyPI packages as conda packages. If available on the specified
        index, the package will be downloaded and converted to a conda package.
        This converted package will then be installed into the active environment.

        Examples:

        Install a single PyPI package into the current conda environment::

            conda pypi install requests

        Install multiple PyPI packages with specific versions::

            conda pypi install "package-a>=12.3"

        """
    )
    install = parser.add_parser(
        "install",
        help=summary,
        description=description,
        epilog=epilog,
    )
    install.add_argument(
        "--index",
        help="PyPI index URL",
        default=DEFAULT_PYPI_INDEX_URL,
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


def execute(args: Namespace) -> int:
    """
    Entry point for the `conda pypi install` subcommand.
    """
    prefix_path = Path(context.target_prefix)

    converter = convert_tree.ConvertTree(
        prefix_path,
        override_channels=args.override_channels,
        index_url=args.index,
    )

    # Convert package strings to MatchSpec objects
    match_specs = [MatchSpec(pkg) for pkg in args.packages]
    channel_url = converter.convert_tree(match_specs)

    # Install converted packages to current conda environment
    run_conda_install(prefix_path, match_specs, channels=[channel_url], override_channels=False)

    return 0
