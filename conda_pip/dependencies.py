"""
"""
import os
import logging
from collections import defaultdict
from contextlib import redirect_stdout, redirect_stderr

from conda.exceptions import CondaError
from grayskull.base.factory import GrayskullFactory
from grayskull.base.pkg_info import is_pkg_available
from grayskull.config import Configuration as GrayskullConfiguration

logging.getLogger("grayskull").setLevel(logging.ERROR)
logging.getLogger("souschef").setLevel(logging.ERROR)
logging.getLogger("requests").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)

# workaround for some weakref leak in souschef
keep_refs_alive = []


def analyze_dependencies(*packages: str):
    conda_deps = defaultdict(set)
    pypi_deps = defaultdict(set)
    for package in packages:
        conda_deps_map, pypi_deps_map, visited_pypi_map = _recursive_dependencies(package)
        for name, dep_set in conda_deps_map.items():
            conda_deps[name].update(dep_set)
        for name, dep_set in pypi_deps_map.items():
            pypi_deps[name].update(dep_set)
        for _, tuples in visited_pypi_map.items():
            for name, version in tuples:
                spec = name
                if version:
                    spec += f"=={version}"
                pypi_deps[name].add(spec)
    return conda_deps, pypi_deps


def _recursive_dependencies(package, conda_deps_map=None, pypi_deps_map=None, visited_pypi_map=None):
    conda_deps_map = conda_deps_map or defaultdict(set)
    pypi_deps_map = pypi_deps_map or defaultdict(set)
    visited_pypi_map = visited_pypi_map or defaultdict(set)
    if package in visited_pypi_map:
        return conda_deps_map, pypi_deps_map, visited_pypi_map
    
    conda_deps, pypi_deps, config = _analyze_with_grayskull(package)
    visited_pypi_map[package].add((config.name, config.version))

    for name, dep in conda_deps.items():
        conda_deps_map[name].add(dep)
    for name, dep in pypi_deps.items():
        pypi_deps_map[name].add(dep)
        _recursive_dependencies(name, conda_deps_map=conda_deps_map, pypi_deps_map=pypi_deps_map, visited_pypi_map=visited_pypi_map)

    return conda_deps_map, pypi_deps_map, visited_pypi_map


def _analyze_with_grayskull(package):
    config = GrayskullConfiguration(name=package, is_strict_cf=True)
    try:
        with redirect_stdout(os.devnull), redirect_stderr(os.devnull):
            recipe = GrayskullFactory.create_recipe("pypi", config)
    except AttributeError as e:
        if "There is no sdist package on pypi" in str(e):
            return {}, {}, config
        raise
    except Exception as e:
        raise CondaError(f"Could not infer deps for {package}") from e

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
    return in_conda, not_in_conda, config
