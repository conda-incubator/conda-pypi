""" """

from __future__ import annotations

import json
import os
from collections import defaultdict
from logging import getLogger
from functools import lru_cache
from io import BytesIO
from typing import Iterable, Literal

import requests
from conda.models.match_spec import MatchSpec
from conda.models.channel import Channel
from conda_libmamba_solver.index import LibMambaIndexHelper as Index
from ruamel.yaml import YAML

from conda_pypi.utils import pypi_spec_variants

# Import functions from pupa module for backward compatibility
from conda_pypi.dependencies.pupa import (
    check_dependencies,
    ensure_requirements,
    MissingDependencyError,
)

__all__ = [
    "BACKENDS",
    "NAME_MAPPINGS",
    "analyze_dependencies",
    "check_dependencies",
    "ensure_requirements",
    "MissingDependencyError",
]

yaml = YAML(typ="safe")
logger = getLogger(f"conda.{__name__}")

BACKENDS = (
    "grayskull",
    "pip",
)
NAME_MAPPINGS = {
    # prioritize grayskull and cf-graph because they contain PyQt version delimiters
    "grayskull": "https://raw.githubusercontent.com/conda/grayskull/main/grayskull/strategy/config.yaml",
    "cf-graph-countyfair": "https://raw.githubusercontent.com/regro/cf-graph-countyfair/master/mappings/pypi/grayskull_pypi_mapping.yaml",
    "parselmouth": "https://raw.githubusercontent.com/prefix-dev/parselmouth/main/files/mapping_as_grayskull.json",
}


def analyze_dependencies(
    *pypi_specs: str,
    editable: str | None = None,
    prefer_on_conda: bool = True,
    channel: str = "conda-forge",
    backend: Literal["grayskull", "pip"] = "pip",
    prefix: str | os.PathLike | None = None,
    force_reinstall: bool = False,
) -> tuple[dict[str, list[str]], dict[str, list[str]], dict[str, list[str]]]:
    conda_deps = defaultdict(list)
    needs_analysis = []
    for pypi_spec in pypi_specs:
        if prefer_on_conda:
            pkg_is_on_conda, conda_spec = _is_pkg_on_conda(pypi_spec, channel=channel)
            if pkg_is_on_conda:
                # TODO: check if version is available too
                logger.info(
                    "Package %s is available on %s as %s. Skipping analysis.",
                    pypi_spec,
                    channel,
                    conda_spec,
                )
                conda_deps[MatchSpec(conda_spec).name].append(conda_spec)
                continue
        needs_analysis.append(pypi_spec)
    if editable:
        needs_analysis.extend(["-e", editable])

    if not needs_analysis:
        return conda_deps, {}, {}

    if backend == "grayskull":
        if editable:
            logger.warning("Ignoring editable=%s with backend=grayskull", editable)
        from conda_pypi.dependencies.grayskull import _analyze_with_grayskull

        found_conda_deps, pypi_deps = _analyze_with_grayskull(
            *needs_analysis, prefer_on_conda=prefer_on_conda, channel=channel
        )
    elif backend == "pip":
        from conda_pypi.dependencies.pip import _analyze_with_pip

        python_deps, pypi_deps, editable_deps = _analyze_with_pip(
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
    editable_deps = editable_deps if editable else {}
    return conda_deps, pypi_deps, editable_deps


def _classify_dependencies(
    deps_from_pypi: dict[str, list[str]],
    prefer_on_conda: bool = True,
    channel: str = "conda-forge",
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    pypi_deps = defaultdict(list)
    conda_deps = defaultdict(list)
    for depname, deps in deps_from_pypi.items():
        if prefer_on_conda:
            on_conda, conda_depname = _is_pkg_on_conda(depname, channel=channel)
            if on_conda:
                deps_mapped_to_conda = [
                    _pypi_spec_to_conda_spec(dep, channel=channel) for dep in deps
                ]
                conda_deps[conda_depname].extend(deps_mapped_to_conda)
                continue
        pypi_deps[depname].extend(deps)
    return conda_deps, pypi_deps


@lru_cache(maxsize=None)
def _is_pkg_on_conda(pypi_spec: str, channel: str = "conda-forge") -> tuple[bool, str]:
    """
    Given a PyPI spec (name, version), try to find it on conda-forge.
    """
    index = Index(channels=[Channel(channel)])
    for spec_variant in pypi_spec_variants(pypi_spec):
        conda_spec = _pypi_spec_to_conda_spec(spec_variant)
        records = index.search(conda_spec)
        if records:
            return True, conda_spec
    return False, pypi_spec


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
    if source in ("grayskull", "cf-graph-countyfair"):
        stream = BytesIO(r.content)
        stream.seek(0)
        data = yaml.load(stream)
        name_key = "conda_forge" if source == "grayskull" else "conda_name"
        mapping = {}
        for pypi, payload in data.items():
            conda_spec_str = payload[name_key]
            if lower_bound := payload.get("delimiter_min"):
                conda_spec_str += f">={lower_bound}"
            if upper_bound := payload.get("delimiter_max"):
                if lower_bound:
                    conda_spec_str += ","
                conda_spec_str += f"<{upper_bound}.0dev0"
            mapping[pypi] = conda_spec_str
        return mapping
    if source == "parselmouth":  # json
        return {pypi: conda for (conda, pypi) in json.loads(r.text).items()}


@lru_cache(maxsize=None)
def _pypi_spec_to_conda_spec(
    spec: str,
    channel: str = "conda-forge",
    sources: Iterable[str] = NAME_MAPPINGS.keys(),
) -> str:
    """
    Tries to find the conda equivalent of a PyPI name. For that it relies
    on known mappings (see `_pypi_to_conda_mapping`). If the PyPI name is
    not found in any of the mappings, we assume the name is the same.

    Note that we don't currently have a way to disambiguate two different
    projects that have the same name in PyPI and conda-forge (e.g. quetz, pixi).
    We could improve this with API calls to metadata servers and compare sources,
    but this is not currently implemented or even feasible.
    """
    assert spec, "Must be non-empty spec"
    assert channel == "conda-forge", "Only channel=conda-forge is supported for now"
    match_spec = MatchSpec(spec)
    conda_name = pypi_name = match_spec.name
    for source in sources:
        mapping = _pypi_to_conda_mapping(source)
        if not mapping:
            continue
        conda_spec = MatchSpec(mapping.get(pypi_name, pypi_name))
        conda_name = conda_spec.name
        if conda_name != pypi_name or not conda_spec.is_name_only_spec:
            renamed = MatchSpec(match_spec, name=conda_name)
            if not conda_spec.is_name_only_spec:
                merged = MatchSpec.merge([renamed, conda_spec])
                if len(merged) > 1:
                    raise ValueError(f"This should not happen: {merged}")
                return str(merged[0])
            return str(renamed)
    return spec
