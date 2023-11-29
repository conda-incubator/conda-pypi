"""
conda pip subcommand for CLI
"""
import argparse
import sys
from logging import getLogger
from pathlib import Path

from conda.cli.common import confirm_yn
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

    from conda.common.io import Spinner
    from conda.models.match_spec import MatchSpec
    from .dependencies import analyze_dependencies
    from .main import validate_target_env, get_prefix, run_conda_install, run_pip_install

    prefix = Path(get_prefix(args.prefix, args.name))
    packages_not_installed = validate_target_env(prefix, args.packages)
    packages_to_process = args.packages if args.force_reinstall else packages_not_installed
    if not packages_to_process:
        print("All packages are already installed.", file=sys.stderr)
        return

    with Spinner("Analyzing dependencies", enabled=not args.quiet, json=args.json):
        conda_deps, pypi_deps = analyze_dependencies(*packages_to_process)

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
   
    if not args.quiet or not args.json:
        if conda_match_specs:
            print("Installable with conda:")
            for spec in conda_match_specs:
                print(" -", spec)
        print("Will install with pip:")
        for spec in pypi_specs:
            print(" -", spec)
    
    if not args.yes and not args.json:
        confirm_yn(dry_run=args.dry_run)

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

    if not args.quiet or not args.json:
        print("Running pip install...")
    return run_pip_install(
        prefix,
        pypi_specs,
        dry_run=args.dry_run,
        quiet=args.quiet,
        verbosity=args.verbosity,
        force_reinstall=args.force_reinstall,
        yes=args.yes,
    )
