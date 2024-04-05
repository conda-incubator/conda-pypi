""" """

from __future__ import annotations

import os
from collections import defaultdict
from logging import getLogger
from functools import lru_cache
from io import BytesIO
from typing import Literal

import requests
from conda.models.match_spec import MatchSpec
from conda_libmamba_solver.index import LibMambaIndexHelper as Index
from ruamel.yaml import YAML

yaml = YAML(typ="safe")
logger = getLogger(f"conda.{__name__}")

BACKENDS = (
    "grayskull",
    "pip",
)
NAME_MAPPINGS = {
    "grayskull": "https://github.com/conda/grayskull/raw/main/grayskull/strategy/config.yaml",
    "cf-graph-countyfair": "https://github.com/regro/cf-graph-countyfair/raw/master/mappings/pypi/grayskull_pypi_mapping.yaml",
}


def analyze_dependencies(
    *packages: str,
    prefer_on_conda: bool = True,
    channel: str = "conda-forge",
    backend: Literal["grayskull", "pip"] = "pip",
    prefix: str | os.PathLike | None = None,
    force_reinstall: bool = False,
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    conda_deps = defaultdict(list)
    needs_analysis = []
    for package in packages:
        match_spec = MatchSpec(package)
        pkg_name = match_spec.name
        # pkg_version = match_spec.version
        if prefer_on_conda and _is_pkg_on_conda(pkg_name, channel=channel):
            # TODO: check if version is available too
            logger.info("Package %s is available on %s. Skipping analysis.", pkg_name, channel)
            conda_spec = _pypi_spec_to_conda_spec(package)
            conda_deps[pkg_name].append(conda_spec)
            continue
        needs_analysis.append(package)

    if not needs_analysis:
        return conda_deps, {}

    if backend == "grayskull":
        from .grayskull import _analyze_with_grayskull

        found_conda_deps, pypi_deps = _analyze_with_grayskull(
            *needs_analysis, prefer_on_conda=prefer_on_conda, channel=channel
        )
    elif backend == "pip":
        from .pip import _analyze_with_pip

        python_deps, pypi_deps = _analyze_with_pip(
            *needs_analysis,
            prefix=prefix,
            force_reinstall=force_reinstall,
        )
        found_conda_deps, pypi_deps = _classify_dependencies(
            pypi_deps,
            prefer_on_conda=prefer_on_conda,
            channel=channel,
        )
        found_conda_deps.update(python_deps)
    else:
        raise ValueError(f"Unknown backend {backend}")

    for name, specs in found_conda_deps.items():
        conda_deps[name].extend(specs)

    # deduplicate
    conda_deps = {name: list(dict.fromkeys(specs)) for name, specs in conda_deps.items()}
    pypi_deps = {name: list(dict.fromkeys(specs)) for name, specs in pypi_deps.items()}
    return conda_deps, pypi_deps


def _classify_dependencies(
    deps_from_pypi: dict[str, list[str]],
    prefer_on_conda: bool = True,
    channel: str = "conda-forge",
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    pypi_deps = defaultdict(list)
    conda_deps = defaultdict(list)
    for depname, deps in deps_from_pypi.items():
        if prefer_on_conda and _is_pkg_on_conda(depname, channel=channel):
            conda_depname = _pypi_spec_to_conda_spec(depname, channel=channel).name
            deps_mapped_to_conda = [_pypi_spec_to_conda_spec(dep, channel=channel) for dep in deps]
            conda_deps[conda_depname].extend(deps_mapped_to_conda)
        else:
            pypi_deps[depname].extend(deps)
    return conda_deps, pypi_deps


@lru_cache(maxsize=None)
def _is_pkg_on_conda(pypi_spec: str, channel: str = "conda-forge"):
    """
    Given a PyPI spec (name, version), try to find it on conda-forge.
    """
    conda_spec = _pypi_spec_to_conda_spec(pypi_spec)
    index = Index(channels=[channel])
    records = index.search(conda_spec)
    return bool(records)


@lru_cache(maxsize=None)
def _pypi_to_conda_mapping(source="grayskull"):
    try:
        url = NAME_MAPPINGS[source]
    except KeyError as exc:
        raise ValueError(f"Invalid source {source}. Allowed: {NAME_MAPPINGS.keys()}") from exc
    r = requests.get(url)
    try:
        r.raise_for_status()
    except requests.HTTPError as exc:
        logger.debug("Could not fetch mapping %s", url, exc_info=exc)
        return {}
    stream = BytesIO(r.content)
    stream.seek(0)
    return yaml.load(stream)


@lru_cache(maxsize=None)
def _pypi_spec_to_conda_spec(spec: str, channel: str = "conda-forge"):
    """
    Tries to find the conda equivalent of a PyPI name. For that it relies
    on known mappings (see `_pypi_to_conda_mapping`). If the PyPI name is
    not found in any of the mappings, we assume the name is the same.

    Note that we don't currently have a way to disambiguate two different
    projects that have the same name in PyPI and conda-forge (e.g. quetz, pixi).
    We could improve this with API calls to metadata servers and compare sources,
    but this is not currently implemented or even feasible.
    """
    assert channel == "conda-forge", "Only channel=conda-forge is supported for now"
    match_spec = MatchSpec(spec)
    conda_name = pypi_name = match_spec.name
    for source in NAME_MAPPINGS:
        mapping = _pypi_to_conda_mapping(source)
        if not mapping:
            continue
        entry = mapping.get(pypi_name, {})
        conda_name = entry.get("conda_forge") or entry.get("conda_name") or pypi_name
        if conda_name != pypi_name:  # we found a match!
            return str(MatchSpec(match_spec, name=conda_name))
    return spec
