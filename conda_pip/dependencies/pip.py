import json
from logging import DEBUG, getLogger
from collections import defaultdict
from subprocess import run

from conda.exceptions import CondaError
from grayskull.base.pkg_info import is_pkg_available

from ..utils import get_env_python

logger = getLogger(f"conda.{__name__}")


def _analyze_with_pip(
    *packages,
    prefer_on_conda=True,
    channel="conda-forge",
    prefix=None,
    force_reinstall=False,
):
    cmd = [
        get_env_python(prefix),
        "-mpip",
        "install",
        "--dry-run",
        "--ignore-installed",
        *(("--force-reinstall",) if force_reinstall else ()),
        "--report",
        "-",  # this tells pip to print the report to stdout
        "--quiet",  # this is needed so normal pip output doesn't get mixed with json
        *packages,
    ]
    process = run(cmd, capture_output=True, text=True, errors="backslashreplace")
    if process.returncode != 0:
        raise CondaError(
            f"Failed to analyze dependencies with pip:\n"
            f"  command: {' '.join(map(str, cmd))}\n"
            f"  exit code: {process.returncode}\n"
            f"  stdout:\n{process.stdout}\n"
            f"  stderr:\n{process.stderr}\n"
        )
    logger.debug(
        "pip (%s) provided the following report:\n%s",
        " ".join(map(str, cmd)),
        process.stdout,
    )
    report = json.loads(process.stdout)
    deps_from_pip = defaultdict(list)
    conda_deps = defaultdict(list)
    for item in report["install"]:
        metadata = item["metadata"]
        logger.debug("Analyzing %s", metadata["name"])
        logger.debug("  metadata: %s", json.dumps(metadata, indent=2))
        deps_from_pip[metadata["name"]].append(f"{metadata['name']}=={metadata['version']}")
        if python_version := metadata.get("requires_python"):
            conda_deps["python"].append(f"python {python_version}")

    deps_from_pip = {name: list(dict.fromkeys(specs)) for name, specs in deps_from_pip.items()}

    pypi_deps = defaultdict(list)
    for depname, deps in deps_from_pip.items():
        if prefer_on_conda and is_pkg_available(depname, channel=channel):
            conda_deps[depname].extend(deps)  # TODO: Map pypi name to conda name(s)
        else:
            pypi_deps[depname].extend(deps)
    return conda_deps, pypi_deps
