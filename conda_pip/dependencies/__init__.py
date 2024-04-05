""" """

from __future__ import annotations

import os
from logging import getLogger
from collections import defaultdict
from typing import Literal

from conda.models.match_spec import MatchSpec


logger = getLogger(f"conda.{__name__}")

BACKENDS = (
    "grayskull",
    "pip",
)


def analyze_dependencies(
    *packages: str,
    prefer_on_conda: bool = True,
    channel: str = "conda-forge",
    backend: Literal["grayskull", "pip"] = "pip",
    prefix: str | os.PathLike | None =None,
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
            conda_deps[pkg_name].append(package)
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
            conda_depname = _pypi_name_to_conda_name(depname, channel=channel)
            deps_mapped_to_conda = [
                _pypi_name_to_conda_name(dep, channel=channel)
                for dep in deps
            ]
            conda_deps[conda_depname].extend(deps_mapped_to_conda)
        else:
            pypi_deps[depname].extend(deps)
    return conda_deps, pypi_deps


def _is_pkg_on_conda(spec: str, channel: str = "conda-forge"):
    # TODO: Do this without grayskull
    from grayskull.base.pkg_info import is_pkg_available

    return is_pkg_available(spec, channel=channel)


def _pypi_name_to_conda_name(spec: str, channel: str = "conda-forge"):
    # TODO: implement mapping
    return spec
