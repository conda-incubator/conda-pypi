"""
Paths we need to know.
"""

from pathlib import Path

import conda.common.path


def get_python_executable(prefix: Path):
    return Path(prefix, conda.common.path.get_python_short_path())
