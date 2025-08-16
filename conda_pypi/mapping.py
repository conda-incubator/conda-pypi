"""
PyPI -> Conda package name mapping using Grayskull data.

This module handles the complex task of translating package names between
PyPI and conda ecosystems using the comprehensive Grayskull mapping database.

"""

from __future__ import annotations

import json
import pkgutil
from typing import Dict, Any, Optional

from packaging.utils import canonicalize_name

# Global cache for the mapping data (lazy-loaded)
_grayskull_mapping: Optional[Dict[str, Dict[str, Any]]] = None
_to_pypi_name_map: Dict[str, Dict[str, Any]] = {}


def get_grayskull_mapping() -> Dict[str, Dict[str, Any]]:
    """
    Lazy load the grayskull mapping data.

    Returns:
        Dictionary mapping PyPI package names to their conda equivalents.
        Each entry contains: pypi_name, conda_name, import_name, mapping_source
    """
    global _grayskull_mapping
    if _grayskull_mapping is None:
        _grayskull_mapping = json.loads(
            pkgutil.get_data("conda_pypi", "grayskull_pypi_mapping.json") or "{}"
        )
    return _grayskull_mapping


def pypi_to_conda_name(pypi_name: str, skip_mapping: bool = False) -> str:
    """
    Convert a PyPI package name to its conda equivalent.

    This function uses the Grayskull mapping database to find the appropriate
    conda package name for a given PyPI package name. This is essential because
    package names can differ between ecosystems.

    Args:
        pypi_name: The PyPI package name to convert
        skip_mapping: If True, skip grayskull mapping and return the original name.
                     This is useful for explicitly requested packages that should
                     be installed from PyPI rather than mapped to conda packages.

    Returns:
        The conda package name equivalent

    Examples:
        >>> pypi_to_conda_name("scikit-learn")
        "scikit-learn"
        >>> pypi_to_conda_name("zope-interface")
        "zope.interface"
        >>> pypi_to_conda_name("unknown-package")
        "unknown-package"
    """
    pypi_name = canonicalize_name(pypi_name)

    if skip_mapping:
        return pypi_name

    mapping = get_grayskull_mapping()
    return mapping.get(
        pypi_name,
        {
            "pypi_name": pypi_name,
            "conda_name": pypi_name,
            "import_name": None,
            "mapping_source": None,
        },
    )["conda_name"]


def conda_to_pypi_name(conda_name: str) -> str:
    """
    Convert a conda package name to its PyPI equivalent.

    This function performs the reverse mapping from conda package names back
    to PyPI package names. It builds a reverse lookup cache on first use.

    Args:
        conda_name: The conda package name to convert

    Returns:
        The PyPI package name equivalent

    Examples:
        >>> conda_to_pypi_name("zope.interface")
        "zope-interface"
        >>> conda_to_pypi_name("scikit-learn")
        "scikit-learn"
    """
    global _to_pypi_name_map

    if not _to_pypi_name_map:
        mapping = get_grayskull_mapping()
        for value in mapping.values():
            conda_name_from_mapping = value["conda_name"]
            _to_pypi_name_map[conda_name_from_mapping] = value

    # Look up in reverse mapping
    found = _to_pypi_name_map.get(conda_name)
    if found:
        return canonicalize_name(found["pypi_name"])

    # If not found, return canonicalized input
    return canonicalize_name(conda_name)


def get_package_mapping_info(pypi_name: str) -> Dict[str, Any]:
    """
    Get complete mapping information for a PyPI package.

    Args:
        pypi_name: The PyPI package name to look up

    Returns:
        Dictionary containing pypi_name, conda_name, import_name, and mapping_source.
        If not found, returns a default structure with the input name.

    Examples:
        >>> get_package_mapping_info("zope-interface")
        {
            "pypi_name": "zope-interface",
            "conda_name": "zope.interface",
            "import_name": "zope.interface",
            "mapping_source": "regro-bot"
        }
    """
    pypi_name = canonicalize_name(pypi_name)
    mapping = get_grayskull_mapping()

    return mapping.get(
        pypi_name,
        {
            "pypi_name": pypi_name,
            "conda_name": pypi_name,
            "import_name": None,
            "mapping_source": None,
        },
    )


def has_mapping(pypi_name: str) -> bool:
    """
    Check if a PyPI package has a mapping in the Grayskull database.

    Args:
        pypi_name: The PyPI package name to check

    Returns:
        True if the package has a mapping, False otherwise
    """
    pypi_name = canonicalize_name(pypi_name)
    mapping = get_grayskull_mapping()
    return pypi_name in mapping


def get_mapping_stats() -> Dict[str, int]:
    """
    Get statistics about the Grayskull mapping database.

    Returns:
        Dictionary with statistics about the mapping database
    """
    mapping = get_grayskull_mapping()

    # Count different mapping sources
    sources = {}
    for entry in mapping.values():
        source = entry.get("mapping_source", "unknown")
        sources[source] = sources.get(source, 0) + 1

    return {
        "total_mappings": len(mapping),
        "mapping_sources": sources,
    }
