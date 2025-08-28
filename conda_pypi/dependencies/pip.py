from __future__ import annotations

import json
from logging import getLogger
from collections import defaultdict
from conda.core.prefix_data import PrefixData
from conda_pypi.main import dry_run_pip_json

logger = getLogger(f"conda.{__name__}")


def _analyze_with_pip(
    *packages: str,
    prefix: str | None = None,
    force_reinstall: bool = False,
) -> tuple[dict[str, list[str]], dict[str, list[str]], dict[str, list[str]]]:
    python_version = ""
    if prefix:
        prefix_data = PrefixData(prefix)
        python_records = list(prefix_data.query("python"))
        if python_records:
            py_ver = python_records[0].version
            # Convert "3.9.18" to "3.9" format expected by pip
            python_version = ".".join(py_ver.split(".")[:2])

    report = dry_run_pip_json(
        ("--prefix", prefix, *packages),
        force_reinstall=force_reinstall,
        python_version=python_version,
    )
    deps_from_pip = defaultdict(list)
    editable_deps = defaultdict(list)
    conda_deps = defaultdict(list)
    for item in report["install"]:
        metadata = item["metadata"]
        logger.debug("Analyzing %s", metadata["name"])
        logger.debug("  metadata: %s", json.dumps(metadata, indent=2))
        if item.get("download_info", {}).get("dir_info", {}).get("editable"):
            editable_deps[metadata["name"]].append(item["download_info"]["url"])
        elif item.get("is_direct"):
            deps_from_pip[metadata["name"]].append(item["download_info"]["url"])
        else:
            deps_from_pip[metadata["name"]].append(f"{metadata['name']}=={metadata['version']}")
        if python_version := metadata.get("requires_python"):
            conda_deps["python"].append(f"python {python_version}")

    deps_from_pip = {
        name: list(dict.fromkeys(specs))
        for name, specs in deps_from_pip.items()
        if name not in editable_deps
    }
    return conda_deps, deps_from_pip, editable_deps
