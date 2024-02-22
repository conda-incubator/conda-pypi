"""
"""
from logging import getLogger
from collections import defaultdict
from conda.models.match_spec import MatchSpec
from grayskull.base.pkg_info import is_pkg_available

logger = getLogger(f"conda.{__name__}")


def analyze_dependencies(
    *packages: str,
    prefer_on_conda=True,
    channel="conda-forge",
    backend="grayskull",
    prefix=None,
):
    conda_deps = defaultdict(list)
    needs_analysis = []
    for package in packages:
        match_spec = MatchSpec(package)
        pkg_name = match_spec.name
        # pkg_version = match_spec.version
        if prefer_on_conda and is_pkg_available(pkg_name, channel=channel):
            # TODO: check if version is available too
            logger.info("Package %s is available on %s. Skipping analysis.", pkg_name, channel)
            conda_deps[pkg_name].append({package})
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

        found_conda_deps, pypi_deps = _analyze_with_pip(
            *needs_analysis, prefer_on_conda=prefer_on_conda, channel=channel, prefix=prefix,
        )
    else:
        raise ValueError(f"Unknown backend {backend}")

    for name, specs in found_conda_deps.items():
        conda_deps[name].extend(specs)
    # deduplicate
    conda_deps = {name: list(dict.fromkeys(specs)) for name, specs in conda_deps.items()}
    pypi_deps = {name: list(dict.fromkeys(specs)) for name, specs in pypi_deps.items()}
    return conda_deps, pypi_deps
