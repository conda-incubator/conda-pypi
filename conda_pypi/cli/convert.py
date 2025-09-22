from argparse import Namespace, _SubParsersAction
from pathlib import Path

from conda.auxlib.ish import dals
from conda.base.context import context
from conda.exceptions import ArgumentError

from conda_pypi import build


def configure_parser(parser: _SubParsersAction) -> None:
    """
    Configure all subcommand arguments and options via argparse
    """
    # convert subcommand
    summary = "Build and convert local Python sdists, wheels or projects to conda packages"
    description = summary
    epilog = dals(
        """
        Examples:

        Convert a PyPI package to conda format without installing::

            conda pypi convert ./requests-2.32.5-py3-none-any.whl

        Convert a local Python project to conda package::

            conda pypi convert ./my-python-project

        Convert a package and save to a specific output folder::

            conda pypi convert --output-folder ./conda-packages ./numpy-2.3.3-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl

        Convert a package from a Git repository::

            git clone https://github.com/user/repo.git
            conda pypi convert ./repo

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
    if not Path(args.project_path).exists():
        raise ArgumentError("PROJECT must be a local path to a sdist, wheel or directory.")

    package_path = build.pypa_to_conda(
        args.project_path,
        distribution="wheel",
        output_path=args.output_folder,
        prefix=prefix_path,
    )
    print(
        f"Conda package at {package_path} built and converted successfully. "
        f"Output folder: {args.output_folder}."
    )
    return 0
