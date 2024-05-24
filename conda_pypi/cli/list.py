import sys
from conda.base.context import context

from .. import __version__
from ..main import pypi_lines_for_explicit_lockfile


def post_command(command: str):
    if command != "list":
        return
    cmd_line = context.raw_data.get("cmd_line", {})
    if "--explicit" not in sys.argv and not cmd_line.get("explicit"):
        return
    if "--no-pip" in sys.argv or not cmd_line.get("pip"):
        return
    checksum = "md5" if ("--md5" in sys.argv or cmd_line.get("md5")) else None
    to_print = pypi_lines_for_explicit_lockfile(context.target_prefix, checksum=checksum)
    if to_print:
        sys.stdout.flush()
        print(f"# The following lines were added by conda-pypi v{__version__}")
        print("# This is an experimental feature subject to change. Do not use in production.")
        print(*to_print, sep="\n")
