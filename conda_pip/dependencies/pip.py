import json
import sys
from logging import getLogger, ERROR
from collections import defaultdict
from subprocess import run
from tempfile import NamedTemporaryFile

from conda.exceptions import CondaError
from grayskull.base.pkg_info import is_pkg_available


getLogger("requests").setLevel(ERROR)
getLogger("urllib3").setLevel(ERROR)
logger = getLogger(f"conda.{__name__}")


def _analyze_with_pip(*packages, prefer_on_conda=True, channel="conda-forge"):
    with NamedTemporaryFile("w+") as f:
        cmd = [
            sys.executable,
            "-mpip",
            "install",
            "--dry-run",
            "--report",
            f.name,
            *packages,
        ]
        process = run(cmd, capture_output=True, text=True)
        if process.returncode != 0:
            raise CondaError(
                f"Failed to analyze dependencies with pip:\n"
                f"  command: {' '.join(cmd)}\n"
                f"  exit code: {process.returncode}\n"
                f"  stdout:\n{process.stdout}\n"
                f"  stderr:\n{process.stderr}\n"
            )
        f.seek(0)
        report = json.load(f)

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
        if is_pkg_available(depname, channel=channel):
            conda_deps[depname].extend(deps)  # TODO: Map pypi name to conda name(s)
        else:
            pypi_deps[depname].extend(deps)
    return conda_deps, pypi_deps
