import logging
import sys
from conda import plugins
from conda.base.context import context

from . import cli
from .main import ensure_target_env_has_externally_managed

logger = logging.getLogger(__name__)


@plugins.hookimpl
def conda_subcommands():
    yield plugins.CondaSubcommand(
        name="pip",
        summary="Install PyPI packages by converting them to .conda format",
        action=cli.execute,
        configure_parser=cli.configure_parser,
    )


@plugins.hookimpl
def conda_post_commands():
    yield plugins.CondaPostCommand(
        name="conda-pypi-ensure-target-env-has-externally-managed",
        action=ensure_target_env_has_externally_managed,
        run_for={"install", "create", "update", "remove"},
    )
    yield plugins.CondaPostCommand(
        name="conda-pypi-list-explicit",
        action=_post_command_list_explicit,
        run_for={"list"},
    )
    yield plugins.CondaPostCommand(
        name="conda-pypi-process-pypi-lines",
        action=_post_command_process_pypi_lines,
        run_for={"install", "create"},
    )


def _post_command_list_explicit(command: str):
    """Post-command hook for 'conda list --explicit' to add PyPI package information."""
    if command != "list":
        return
    cmd_line = context.raw_data.get("cmd_line", {})
    explicit_arg = cmd_line.get("explicit")
    if "--explicit" not in sys.argv and not (explicit_arg and explicit_arg.value(None)):
        return
    if "--no-pip" in sys.argv:
        return
    md5_arg = cmd_line.get("md5")
    checksums = ("md5",) if ("--md5" in sys.argv or (md5_arg and md5_arg.value(None))) else None

    from .main import pypi_lines_for_explicit_lockfile
    from . import __version__

    to_print = pypi_lines_for_explicit_lockfile(context.target_prefix, checksums=checksums)
    if to_print:
        sys.stdout.flush()
        print(f"# The following lines were added by conda-pypi v{__version__}")
        print("# This is an experimental feature subject to change. Do not use in production.")
        for line in to_print:
            print(line)


def _post_command_process_pypi_lines(command: str):
    """Post-command hook to process PyPI lines from lockfiles during install/create."""
    if command not in ("install", "create"):
        return

    pypi_lines = _pypi_lines_from_paths()
    if not pypi_lines:
        return

    # Import here to avoid circular imports
    import argparse
    from .cli import execute_install

    if not context.quiet:
        logger.info("Preparing PyPI transaction")

    # Create args object similar to what execute_install expects
    args = argparse.Namespace(
        packages=pypi_lines,
        prefix=context.target_prefix,
        name=None,
        override_channels=False,
        quiet=context.quiet,
        json=context.json,
        dry_run=context.dry_run,
        editable=None,  # Not installing editable packages from lockfiles
        subcmd="install",
    )

    # Use our existing install logic to handle PyPI packages
    try:
        if not context.quiet:
            logger.info("Executing PyPI transaction")
        execute_install(args)
        if not context.quiet:
            logger.info("Verifying PyPI transaction")
    except Exception as e:
        if not context.quiet:
            logger.error(f"Failed to install PyPI packages: {e}")


def _pypi_lines_from_paths(paths=None):
    """Extract PyPI lines from lockfiles.

    Args:
        paths: Optional list of file paths to process. If None, extracts from command line.

    Returns:
        List of PyPI package specifications extracted from lockfiles.
    """
    if paths is None:
        file_arg = context.raw_data.get("cmd_line", {}).get("file")
        if file_arg is None:
            return []
        paths = file_arg.value(None) if hasattr(file_arg, "value") else file_arg

    if not paths:
        return []

    lines = []
    line_prefix = "# pypi: "

    for path in paths:
        path_str = path.value(None) if hasattr(path, "value") else str(path)
        try:
            with open(path_str, encoding="utf-8") as f:
                for line in f:
                    if line.startswith(line_prefix):
                        # Extract just the package spec part
                        pypi_spec = line[len(line_prefix) :].strip()
                        # Parse the spec to get just the package name and version
                        # Remove pip-specific flags like --python-version, --record-checksum
                        if " --" in pypi_spec:
                            package_spec = pypi_spec.split(" --")[0]
                        else:
                            package_spec = pypi_spec

                        if package_spec:
                            lines.append(package_spec)
        except OSError as exc:
            if not context.quiet:
                logger.warning(f"Could not process {path_str}: {exc}")

    return lines
