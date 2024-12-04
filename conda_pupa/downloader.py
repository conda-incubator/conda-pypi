"""
Fetch matching wheels from pypi.
"""

import subprocess
import sys
from pathlib import Path

from conda.models.match_spec import MatchSpec

from conda_pupa.translate import conda_to_requires


def download_pypi_pip(matchspec: MatchSpec, target_path: Path):
    """
    Prototype download wheel for missing package using pip.

    Complete implementation should match wheels based on target environment at
    least, directly use pypi API instead of pip.
    """
    requirement = conda_to_requires(matchspec)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--only-binary",
            ":all:",
            "-w",
            str(target_path),
            str(requirement),
        ],
        check=True,
    )
