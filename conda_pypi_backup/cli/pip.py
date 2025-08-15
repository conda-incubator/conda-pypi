"""
conda pip subcommand for CLI
"""

from __future__ import annotations

import argparse
import os
import sys
from logging import getLogger

from conda.cli.common import confirm_yn
from conda.cli.conda_argparse import (
    add_output_and_prompt_options,
    add_parser_help,
    add_parser_prefix,
)
from conda.exceptions import ArgumentError

logger = getLogger(f"conda.{__name__}")


def configure_parser(parser: argparse.ArgumentParser):
    from ..dependencies import BACKENDS

    add_parser_help(parser)
    add_parser_prefix(parser)
    add_output_and_prompt_options(parser)

    subparser = parser.add_subparsers(dest="subcmd", required=True)

    install = subparser.add_parser(
        "install",
        help="Install a PyPI package, archive or URL, "
        "but try to fetch dependencies from conda whenever possible.",
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
        "--force-with-pip",
        action="store_true",
        help="Install packages with pip even they are available on conda. "
        "Only applies to explicitly requested packages, not their dependencies.",
    )
    install.add_argument(
        "--conda-channel",
        metavar="CHANNEL",
        default="conda-forge",
        help="Where to look for conda dependencies.",
    )
    install.add_argument(
        "-e",
        "--editable",
        metavar="<path/url>",
        help="Install a project in editable mode (i.e. setuptools 'develop mode') "
        "from a local project path or a VCS url.",
    )
    install.add_argument(
        "--backend",
        metavar="TOOL",
        default="pip",
        choices=BACKENDS,
        help="Which tool to use for PyPI packaging dependency resolution.",
    )
    install.add_argument("packages", metavar="package", nargs="*")


def execute(args: argparse.Namespace) -> int:
    if not args.packages and not args.editable:
        raise ArgumentError(
            "No packages requested. Please provide one or more packages, "
            "or one editable specification."
        )
    if args.editable and args.backend == "grayskull":
        raise ArgumentError(
            "--editable PKG and --backend=grayskull are not compatible. Please use --backend=pip."
        )

    from conda.common.io import Spinner
    from conda.models.match_spec import MatchSpec
    from ..dependencies import analyze_dependencies
    from ..main import (
        validate_target_env,
        ensure_externally_managed,
        run_conda_install,
        run_pip_install,
    )
    from ..utils import get_prefix

    prefix = get_prefix(args.prefix, args.name)
    packages_not_installed = validate_target_env(prefix, args.packages)

    packages_to_process = args.packages if args.force_reinstall else packages_not_installed
    if not packages_to_process and not args.editable:
        print("All packages are already installed.", file=sys.stderr)
        return 0

    with Spinner("Analyzing dependencies", enabled=not args.quiet, json=args.json):
        conda_deps, pypi_deps, editable_deps = analyze_dependencies(
            *packages_to_process,
            editable=args.editable,
            prefer_on_conda=not args.force_with_pip,
            channel=args.conda_channel,
            backend=args.backend,
            prefix=prefix,
            force_reinstall=args.force_reinstall,
        )

    conda_match_specs = []
    for name, specs in conda_deps.items():
        if name == "python":
            continue  # TODO: check if compatible with target env python
        conda_match_specs.extend(MatchSpec.merge([str(spec) for spec in specs]))

    pypi_specs = []
    for name, specs in pypi_deps.items():
        if (req := set(specs) & set(args.packages)) and "==" in (req := req.pop()):
            # prefer user requested spec if it's one of the choices and it's version explicit
            spec = req
        else:
            spec = specs[0]
            if len(specs) > 1:
                logger.warning("ignoring extra specifiers for %s: %s", name, specs[1:])
        spec = spec.replace(" ", "")  # remove spaces
        pypi_specs.append(spec)
    for name, specs in editable_deps.items():
        for spec in specs:
            pypi_specs.append(f"--editable={spec}")

    if not args.quiet or not args.json:
        if conda_match_specs:
            print("conda will install:")
            for spec in conda_match_specs:
                print(" -", spec)
        if pypi_specs:
            print("pip will install:")
            for spec in pypi_specs:
                print(" -", spec)

    if not args.yes and not args.json:
        if conda_match_specs or pypi_specs:
            confirm_yn(dry_run=False)  # we let conda handle the dry-run exit below
        else:
            print("Nothing to do.", file=sys.stderr)
            return 0

    if conda_match_specs:
        if not args.quiet or not args.json:
            print("Running conda install...")
        retcode = run_conda_install(
            prefix,
            conda_match_specs,
            dry_run=args.dry_run,
            quiet=args.quiet,
            verbosity=args.verbosity,
            force_reinstall=args.force_reinstall,
            yes=args.yes,
            json=args.json,
        )
        if retcode:
            return retcode

    if pypi_specs:
        if not args.quiet or not args.json:
            print("Running pip install...")
        process = run_pip_install(
            prefix,
            pypi_specs,
            dry_run=args.dry_run,
            quiet=args.quiet,
            verbosity=args.verbosity,
            force_reinstall=args.force_reinstall,
            yes=args.yes,
        )
        if process.returncode:
            return process.returncode
        if os.environ.get("CONDA_BUILD_STATE") != "BUILD":
            ensure_externally_managed(prefix)
    return 0
