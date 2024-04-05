import json
import os
from logging import getLogger
from collections import defaultdict
from subprocess import run
from tempfile import NamedTemporaryFile

from conda.exceptions import CondaError

from ..utils import get_env_python

logger = getLogger(f"conda.{__name__}")


def _analyze_with_pip(
    *packages: str,
    prefix: str | None = None,
    force_reinstall: bool = False,
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    # pip can output to stdout via `--report -` (dash), but this
    # creates issues on Windows due to undecodable characters on some
    # project descriptions (e.g. charset-normalizer, amusingly), which
    # makes pip crash internally. Probably a bug on their end.
    # So we use a temporary file instead to work with bytes.
    json_output = NamedTemporaryFile(suffix=".json", delete=False)
    json_output.close()  # Prevent access errors on Windows

    cmd = [
        str(get_env_python(prefix)),
        "-mpip",
        "install",
        "--dry-run",
        "--ignore-installed",
        *(("--force-reinstall",) if force_reinstall else ()),
        "--report",
        json_output.name,
        *packages,
    ]
    process = run(cmd, capture_output=True, text=True)
    if process.returncode != 0:
        raise CondaError(
            f"Failed to analyze dependencies with pip:\n"
            f"  command: {' '.join(cmd)}\n"
            f"  exit code: {process.returncode}\n"
            f"  stderr:\n{process.stderr}\n"
            f"  stdout:\n{process.stdout}\n"
        )
    logger.debug("pip (%s) provided the following report:\n%s", " ".join(cmd), process.stdout)

    with open(json_output.name, "rb") as f:
        # We need binary mode because the JSON output might
        # contain weird unicode stuff (as part of the project
        # description or README).
        report = json.loads(f.read())
    os.unlink(json_output.name)

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
    return conda_deps, deps_from_pip
