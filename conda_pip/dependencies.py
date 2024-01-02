"""
"""
import os
from logging import getLogger, ERROR
from collections import defaultdict
from contextlib import redirect_stdout, redirect_stderr

from conda.exceptions import CondaError
from conda.models.match_spec import MatchSpec
from grayskull.base.factory import GrayskullFactory
from grayskull.base.pkg_info import is_pkg_available
from grayskull.config import Configuration as GrayskullConfiguration

getLogger("grayskull").setLevel(ERROR)
getLogger("souschef").setLevel(ERROR)
getLogger("requests").setLevel(ERROR)
getLogger("urllib3").setLevel(ERROR)
logger = getLogger(f"conda.{__name__}")

# workaround for some weakref leak in souschef
keep_refs_alive = []


def analyze_dependencies(*packages: str, prefer_on_conda=True, channel="conda-forge", backend="grayskull"):
    conda_deps = defaultdict(list)
    pypi_deps = defaultdict(list)
    for package in packages:
        match_spec = MatchSpec(package)
        pkg_name = match_spec.name
        pkg_version = match_spec.version
        if prefer_on_conda and is_pkg_available(pkg_name, channel=channel):
            # TODO: check if version is available too
            logger.info("Package %s is available on %s. Skipping analysis.", pkg_name, channel)
            conda_deps[pkg_name].append(f"{channel}::{package}")
            continue
        conda_deps_map, pypi_deps_map, visited_pypi_map = _recursive_dependencies(pkg_name, pkg_version)
        for name, specs in conda_deps_map.items():
            conda_deps[name].extend(specs)
        for name, specs in pypi_deps_map.items():
            pypi_deps[name].extend(specs)
        for _, tuples in visited_pypi_map.items():
            for name, version in tuples:
                spec = name
                if version:
                    spec += f"=={version}"
                pypi_deps[name].append(spec)

    # deduplicate
    conda_deps = {name: list(dict.fromkeys(specs)) for name, specs in conda_deps.items()}
    pypi_deps = {name: list(dict.fromkeys(specs)) for name, specs in pypi_deps.items()}

    return conda_deps, pypi_deps


def _recursive_dependencies(
    pkg_name,
    pkg_version="",
    conda_deps_map=None,
    pypi_deps_map=None,
    visited_pypi_map=None,
):
    conda_deps_map = conda_deps_map or defaultdict(list)
    pypi_deps_map = pypi_deps_map or defaultdict(list)
    visited_pypi_map = visited_pypi_map or defaultdict(list)
    if (pkg_name, pkg_version) in visited_pypi_map:
        return conda_deps_map, pypi_deps_map, visited_pypi_map

    conda_deps, pypi_deps, config = _analyze_with_grayskull(pkg_name, pkg_version)
    visited_pypi_map[(pkg_name, pkg_version)].append((config.name, config.version))

    for name, dep in conda_deps.items():
        conda_deps_map[name].append(dep)
    for name, dep in pypi_deps.items():
        pypi_deps_map[name].append(dep)
        _recursive_dependencies(
            name,
            conda_deps_map=conda_deps_map,
            pypi_deps_map=pypi_deps_map,
            visited_pypi_map=visited_pypi_map,
        )

    return conda_deps_map, pypi_deps_map, visited_pypi_map


def _analyze_with_grayskull(package, version=""):
    config = GrayskullConfiguration(name=package, version=version, is_strict_cf=True)
    try:
        with redirect_stdout(os.devnull), redirect_stderr(os.devnull):
            recipe = GrayskullFactory.create_recipe("pypi", config)
    except AttributeError as e:
        if "There is no sdist package on pypi" in str(e):
            return {}, {}, config
        raise
    except Exception as e:
        raise CondaError(f"Could not infer deps for {package}:\n{e}") from e

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
            in_conda[name] = str(dep)
        elif is_pkg_available(name):
            in_conda[name] = str(dep)
        else:
            not_in_conda[name] = str(dep)
    return in_conda, not_in_conda, config
