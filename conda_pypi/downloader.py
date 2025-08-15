"""
Fetch matching wheels from pypi.
"""

from pathlib import Path

from conda.core.prefix_data import get_python_version_for_prefix
from conda.gateways.connection.download import download
from conda.models.match_spec import MatchSpec
from unearth import PackageFinder, TargetPython

from conda_pupa.translate import conda_to_requires

from .exceptions import PupaError


def get_package_finder(prefix: Path):
    """
    Finder with prefix's Python, not our Python.
    """
    py_ver = get_python_version_for_prefix(prefix)
    if not py_ver:
        raise PupaError(f"Python not found in {prefix}")
    py_ver = tuple(map(int, py_ver.split(".")))
    target_python = TargetPython(py_ver=py_ver)
    return PackageFinder(target_python=target_python, only_binary=":all:")


def find_package(finder: PackageFinder, package: str):
    """
    Convert :package: to `MatchSpec`; return best `Link`.
    """
    spec = MatchSpec(package)  # type: ignore # metaclass confuses type checker
    requirement = conda_to_requires(spec)
    if not requirement:
        raise RuntimeError(f"Could not convert {package} to Python Requirement()!")
    return finder.find_best_match(requirement)


def find_and_fetch(finder: PackageFinder, target: Path, package: str):
    """
    Find package on PyPI, download best link to target.
    """
    result = find_package(finder, package)
    link = result.best and result.best.link
    if not link:
        raise PupaError(f"No PyPI link for {package}")
    filename = link.url_without_fragment.rsplit("/", 1)[-1]
    print(f"Fetch {package} as {filename}")
    download(link.url, target / filename)
