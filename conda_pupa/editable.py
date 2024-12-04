"""
Build a Python project into an editable wheel, convert to a .conda and install
the .conda.
"""

import sys
from pathlib import Path

from .build import pypa_to_conda


# Older name, distribution doesn't have to be 'editable'
def editable(project: Path | str, distribution="editable"):
    return pypa_to_conda(project, distribution=distribution)


# XXX Could we set CONDA_PKGS_DIRS=(temporary directory), (standard locations)
# to defeat "ephemeral package is cached" logic when installing an editable
# conda


if __name__ == "__main__":  # pragma: no cover
    editable(sys.argv[1])
