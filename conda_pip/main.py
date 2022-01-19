"""
"""

from collections import defaultdict
import logging

from grayskull.base.factory import GrayskullFactory
from grayskull.base.pkg_info import is_pkg_available
from grayskull.config import Configuration as GrayskullConfiguration

logging.getLogger("grayskull").setLevel(logging.ERROR)
logging.getLogger("souschef").setLevel(logging.ERROR)
logging.getLogger("requests").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)

# workaround for some weakref leak in souschef
keep_refs_alive = []


def install(*packages: str):
    conda_deps = defaultdict(set)
    pypi_deps = defaultdict(set)
    for package in packages:
        conda_deps_map, pypi_deps_map = _install_one(package)
        for name, dep_set in conda_deps_map.items():
            conda_deps[name].update(dep_set)
        for name, dep_set in pypi_deps_map.items():
            pypi_deps[name].update(dep_set)
    return conda_deps, pypi_deps


def _install_one(package, conda_deps_map=None, pypi_deps_map=None):
    conda_deps_map = conda_deps_map or defaultdict(set)
    pypi_deps_map = pypi_deps_map or defaultdict(set)
    conda_deps, pypi_deps = infer_dependencies_in_conda(package)

    for name, dep in conda_deps.items():
        conda_deps_map[name].add(dep)
    for name, dep in pypi_deps.items():
        pypi_deps_map[name].add(dep)
        _install_one(name, conda_deps_map=conda_deps_map, pypi_deps_map=pypi_deps_map)

    return conda_deps_map, pypi_deps_map


def infer_dependencies_in_conda(package):
    config = GrayskullConfiguration(package, is_strict_cf=True)
    recipe = GrayskullFactory.create_recipe("pypi", config)
    global keep_refs_alive
    keep_refs_alive.append(recipe)

    requirements = recipe["requirements"]
    in_conda = {}
    not_in_conda = {}
    for dep in requirements["run"]:
        name = dep.package_name
        if name.startswith(("<{", "{{")):  # jinja package
            if "pin_compatible" in dep.value:
                name = dep.value.split("(")[1].split(")")[0].strip("'\"")
                dep = next(hdep for hdep in requirements["host"] if hdep.package_name == name)
            else:
                print("skipping", dep)
                continue
        if name in ("python", "numpy"):
            in_conda[name] = dep
        elif is_pkg_available(name):
            in_conda[name] = dep
        else:
            not_in_conda[name] = dep
    return in_conda, not_in_conda
