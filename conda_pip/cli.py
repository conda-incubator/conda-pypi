"""
conda pip subcommand for CLI
"""
import argparse
import os
import sys
from subprocess import run
from logging import getLogger

from conda.cli.conda_argparse import (
    add_output_and_prompt_options,
    add_parser_help,
    add_parser_prefix,
)

logger = getLogger(f"conda.{__name__}")


def configure_parser(parser: argparse.ArgumentParser):
    add_parser_help(parser)
    add_parser_prefix(parser)
    add_output_and_prompt_options(parser)

    subparser = parser.add_subparsers(dest="subcmd")

    install = subparser.add_parser(
        "install",
        help="Install a PyPI package, archive or URL.",
    )
    install.add_argument("-U", "--upgrade", action="store_true")
    install.add_argument("--force-reinstall", action="store_true")
    install.add_argument("packages", nargs="+")


def execute(args: argparse.Namespace) -> None:
    if not args.packages:
        return

    from conda.base.context import context, locate_prefix_by_name
    from conda.common.io import Spinner
    from conda.core.prefix_data import PrefixData
    from conda.models.match_spec import MatchSpec
    from .dependencies import analyze_dependencies

    if args.force_reinstall:
        packages_to_process = args.packages
    else:
        context.validate_configuration()
        pd = PrefixData(context.target_prefix, pip_interop_enabled=True)
        packages_to_process = []
        for pkg in args.packages:
            spec = MatchSpec(pkg)
            if list(pd.query(spec)):
                logger.warning("package %s is already installed; ignoring", spec)
                continue
            packages_to_process.append(pkg)
    if not packages_to_process:
        print("All packages are already installed.", file=sys.stderr)
        return
    with Spinner("Analyzing dependencies", enabled=not args.quiet, json=args.json):
        conda_deps, pypi_deps = analyze_dependencies(*packages_to_process)
    conda_match_specs = []
    for name, depset in conda_deps.items():
        if name == "python":
            continue  # TODO: check if compatible with target env python
        conda_match_specs.extend(MatchSpec.merge([str(dep) for dep in depset]))
    if not args.quiet or not args.json:
        if conda_match_specs:
            print("Installable with conda:")
            for spec in conda_match_specs:
                print(" -", spec)
        print("Will install with pip:")
        for name, depset in pypi_deps.items():
            if len(depset) == 1:
                print(" -", next(iter(depset)))
            else:
                print(" -", name, "# ignoring:", *depset)

    if args.prefix:
        target_env = ("--prefix", args.prefix)
    elif args.name:
        prefix = locate_prefix_by_name(args.name)
        target_env = ("--prefix", prefix)
    else:
        target_env = ("--prefix", context.target_prefix)

    if not args.quiet or not args.json:
        print("Running conda install...")
    verbosity = ("-" + ("v" * args.verbosity),) if args.verbosity else ()
    quiet = ["--quiet"] if args.quiet else []
    dry_run = ["--dry-run"] if args.dry_run else []
    force_reinstall = ["--force-reinstall"] if args.force_reinstall else []

    if conda_match_specs:
        command = [
            "install",
            *dry_run,
            *quiet,
            *verbosity,
            *force_reinstall,
            *target_env,
            *(["--yes"] if args.yes else []),
            *(["--json"] if args.json else []),
            *[str(spec) for spec in conda_match_specs],
        ]
        from conda.cli.python_api import run_command

        logger.info("conda install command: conda %s", command)
        run_command(*command, stdout=None, stderr=None, use_exception_handler=True)

    if not args.quiet or not args.json:
        print("Running pip install...")
    pypi_specs = []
    for name, depset in pypi_deps.items():
        pypi_specs.append(str(next(iter(depset))))
        if len(depset) > 1:
            logger.warning("ignoring multiple specifiers for %s: %s", name, depset)
    target_python = os.path.join(target_env[1], "bin", "python")
    command = [
        target_python,
        "-mpip",
        "install",
        *dry_run,
        *quiet,
        *verbosity,
        *force_reinstall,
        *target_env,
        "--no-deps",
        *(["--upgrade"] if args.upgrade else []),
        *pypi_specs,
    ]
    logger.info("pip install command: %s", command)
    run(command, check=True)
