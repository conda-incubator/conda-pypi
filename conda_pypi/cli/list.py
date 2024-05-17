import sys

from conda.base.context import context

from ..main import pypi_lines_for_explicit_lockfile

def post_command(command: str):
    if command != "list":
        return
    if "--explicit" not in sys.argv:
        return
    to_print = pypi_lines_for_explicit_lockfile(context.target_prefix)

    if to_print:
        print("# Following lines added by conda-pypi")
        print(*to_print, sep="\n")
