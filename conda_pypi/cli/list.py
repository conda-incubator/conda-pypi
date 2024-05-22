import sys

from conda.base.context import context

from .. import __version__
from ..main import pypi_lines_for_explicit_lockfile

def post_command(command: str):
    if command != "list":
        return
    if "--explicit" not in sys.argv:
        return
    to_print = pypi_lines_for_explicit_lockfile(context.target_prefix)

    if to_print:
        print(f"# The following lines were added by conda-pypi v{__version__}")
        print("# This is an experimental feature subject to change. Do not use in production.")
        print(*to_print, sep="\n")
