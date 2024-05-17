from __future__ import annotations

import json
from logging import getLogger
from collections import defaultdict
from ..main import dry_run_pip_json

logger = getLogger(f"conda.{__name__}")


def _analyze_with_pip(
    *packages: str,
    prefix: str | None = None,
    force_reinstall: bool = False,
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    report = dry_run_pip_json(prefix, packages, force_reinstall)
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
