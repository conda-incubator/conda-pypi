from argparse import Namespace, _SubParsersAction
from pathlib import Path

from conda.auxlib.ish import dals
from conda.base.context import context

from conda_pypi import build


def configure_parser(parser: _SubParsersAction) -> None:
    """
    Configure all subcommand arguments and options via argparse
    """
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

    convert = parser.add_parser(
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


def execute(args: Namespace) -> int:
    """
    Entry point for the `conda pypi convert` subcommand
    """
    prefix_path = Path(context.target_prefix)

    package_path = build.pypa_to_conda(
        args.project_path,
        distribution="wheel",
        output_path=args.output_folder,
        prefix=prefix_path,
    )
    print(
        f"Conda package at {package_path} built and converted successfully.  Output folder: {args.output_folder}"
    )
    return 0
