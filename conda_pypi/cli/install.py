import tempfile
from argparse import _SubParsersAction, Namespace
from pathlib import Path

from conda.auxlib.ish import dals
from conda.models.match_spec import MatchSpec

from conda_pypi import convert_tree, build, installer
from conda_pypi.downloader import get_package_finder
from conda_pypi.main import run_conda_install
from conda_pypi.utils import get_prefix


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

        Install a local project in editable mode::

            conda pypi install -e ./my-project

        Install the current directory in editable mode::

            conda pypi install -e .

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
        nargs="*",
        help="PyPI packages to install",
    )
    install.add_argument(
        "-p",
        "--prefix",
        help="Full path to environment location (i.e. prefix).",
        required=False,
    )
    install.add_argument(
        "-e",
        "--editable",
        help="Build and install named path as an editable package, linking project into environment.",
    )


def execute(args: Namespace) -> int:
    """
    Entry point for the `conda pypi install` subcommand.
    """
    if not args.editable and not args.packages:
        raise SystemExit(2)

    prefix_path = get_prefix()

    if args.editable:
        editable_path = Path(args.editable).expanduser()
        output_path_manager = tempfile.TemporaryDirectory("conda-pypi")
        with output_path_manager as output_path:
            package = build.pypa_to_conda(
                editable_path,
                distribution="editable",
                output_path=Path(output_path),
                prefix=prefix_path,
            )
            installer.install_ephemeral_conda(prefix_path, package)
        return 0

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
    changes = converter.convert_tree(match_specs)
    channel_url = converter.repo.as_uri()

    if changes is None:
        packages_to_install = ()
    else:
        packages_to_install = changes[1]
    converted_packages = [
        str(pkg.to_simple_match_spec())
        for pkg in packages_to_install
        if pkg.channel.canonical_name == channel_url
    ]
    if converted_packages:
        converted_packages_dashed = "\n - ".join(converted_packages)
        print(f"Converted packages\n - {converted_packages_dashed}\n")
    print("Installing environment")

    # Install converted packages to current conda environment
    return run_conda_install(
        prefix_path,
        match_specs,
        channels=[channel_url],
        override_channels=args.override_channels,
        yes=args.yes,
        quiet=args.quiet,
        verbosity=args.verbosity,
        dry_run=args.dry_run,
    )
