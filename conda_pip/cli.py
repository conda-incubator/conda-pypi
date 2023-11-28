"""
conda pip subcommand for CLI
"""
import argparse
import sys
from subprocess import run, PIPE
from logging import getLogger

from conda.cli.conda_argparse import (
    add_output_and_prompt_options,
    add_parser_help,
    add_parser_prefix,
)
from conda.models.match_spec import MatchSpec

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
    install.add_argument("packages", nargs="+")


def execute(args: argparse.Namespace) -> None:
    if not args.packages:
        return

    from conda.common.io import Spinner
    from .dependencies import analyze_dependencies

    with Spinner("Analyzing dependencies", enabled=not args.quiet, json=args.json):
        conda_deps, pypi_deps = analyze_dependencies(*args.packages)
    conda_match_specs = []
    for name, depset in conda_deps.items():
        conda_match_specs.extend(MatchSpec.merge([str(dep) for dep in depset]))

    if not args.quiet or not args.json:
        if conda_match_specs:
            print("Installable with conda:")
            for spec in conda_match_specs:
                print(" -", spec)
        if pypi_deps:
            print("Will install via `pip`:")
            for name, depset in pypi_deps.items():
                if len(depset) == 1:
                    print(" -", next(iter(depset)))
                else:
                    print(" -", name, "# ignoring:", *depset)

    if args.prefix:
        target_env = (f"--prefix={args.prefix}",)
    elif args.name:
        target_env = (f"--name={args.name}",)
    else:
        target_env = ()

    if not args.quiet or not args.json:
        print("Running conda install...")
    verbosity = ("-" + ("v" * args.verbosity),) if args.verbosity else ()
    quiet = ["--quiet"] if args.quiet else []
    dry_run = ["--dry-run"] if args.dry_run else []
    command = [
        sys.executable,
        "-mconda",
        "install",
        *dry_run,
        *quiet,
        *verbosity,
        *target_env,
        *(["--yes"] if args.yes else []),
        *(["--json"] if args.json else []),
        *[str(spec) for spec in conda_match_specs],
    ]
    logger.info("conda install command: %s", command)
    run(command, check=True)
    if not pypi_deps:
        return

    if not args.quiet or not args.json:
        print("Running pip install...")
    pypi_specs = []
    for name, depset in pypi_deps.items():
        pypi_specs.append(next(iter(depset)))
        logger.warning("ignoring multiple specifiers for %s: %s", name, depset)
    command = [
        sys.executable,
        "-mpip",
        "install",
        *dry_run,
        *quiet,
        *verbosity,
        "--no-deps",
        *pypi_specs,
    ]
    logger.info("pip install command: %s", command)
    run(command, check=True)
