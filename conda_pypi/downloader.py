"""
Fetch matching wheels from pypi.
"""

from pathlib import Path

from conda.core.prefix_data import PrefixData
from conda.gateways.connection.download import download
from conda.models.match_spec import MatchSpec
from unearth import PackageFinder, TargetPython

from conda_pypi.translate import conda_to_requires

from conda_pypi.exceptions import CondaPypiError


def get_package_finder(prefix: Path):
    """
    Finder with prefix's Python, not our Python.
    """
    prefix_data = PrefixData(prefix)
    python_records = list(prefix_data.query("python"))
    if not python_records:
        raise CondaPypiError(f"Python not found in {prefix}")
    py_ver = python_records[0].version
    py_ver = tuple(map(int, py_ver.split(".")))
    target_python = TargetPython(py_ver=py_ver)
    return PackageFinder(
        target_python=target_python, only_binary=":all:", index_urls=["https://pypi.org/simple/"]
    )


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
        raise CondaPypiError(f"No PyPI link for {package}")
    filename = link.url_without_fragment.rsplit("/", 1)[-1]
    print(f"Fetch {package} as {filename}")
    download(link.url, target / filename)
