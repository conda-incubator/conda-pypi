"""
Convert Python *.dist-info/METADATA to conda info/index.json
"""

import dataclasses
import json
import logging
import pkgutil
import sys
import time
from importlib.metadata import Distribution, PackageMetadata, PathDistribution
from pathlib import Path
from typing import Any

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

log = logging.getLogger(__name__)


class FileDistribution(Distribution):
    """
    From a file e.g. a single .metadata fetched from pypi instead of a
    *.dist-info folder.
    """

    def __init__(self, raw_text):
        self.raw_text = raw_text

    def read_text(self, filename: str) -> str | None:
        if filename == "METADATA":
            return self.raw_text
        else:
            return None

    def locate_file(self, path):
        """
        Given a path to a file in this distribution, return a path
        to it.
        """
        return None


@dataclasses.dataclass
class PackageRecord:
    # what goes in info/index.json
    name: str
    version: str
    subdir: str
    depends: list[str]
    extras: dict[str, list[str]]
    build_number: int = 0
    build: str = "0"
    license_family: str = ""
    license: str = ""
    noarch: str = ""
    timestamp: int = 0

    def to_index_json(self):
        return {
            "build_number": self.build_number,
            "build": self.build,
            "depends": self.depends,
            "extras": self.extras,
            "license_family": self.license_family,
            "license": self.license,
            "name": self.name,
            "noarch": self.noarch,
            "subdir": self.subdir,
            "timestamp": self.timestamp,
            "version": self.version,
        }

    @property
    def stem(self):
        return f"{self.name}-{self.version}-{self.build}"


@dataclasses.dataclass
class CondaMetadata:
    metadata: PackageMetadata
    console_scripts: list[str]
    package_record: PackageRecord
    about: dict[str, Any]

    @classmethod
    def from_distribution(cls, distribution: Distribution):
        metadata = distribution.metadata

        python_version = metadata["requires-python"]
        requires_python = "python"
        if python_version:
            requires_python = f"python { python_version }"

        requirements, extras = requires_to_conda(distribution.requires)

        # conda does support ~=3.0.0 "compatibility release" matches
        depends = [requires_python] + requirements

        console_scripts = [
            f"{ep.name} = {ep.value}"
            for ep in distribution.entry_points
            if ep.group == "console_scripts"
        ]

        noarch = "python"

        about = {
            "summary": metadata.get("summary"),
            "license": metadata.get("license"),
            # there are two license-file in grayskull e.g.
            "license_file": metadata.get("license_file"),
        }

        name = pypi_to_conda_name(distribution.name)
        version = distribution.version

        package_record = PackageRecord(
            build="0",
            build_number=0,
            depends=depends,
            extras=extras,
            license=about["license"] or "",
            license_family="",
            name=name,
            version=version,
            subdir="noarch",
            noarch=noarch,
            timestamp=time.time_ns() // 1000000,
        )

        return cls(
            metadata=metadata,
            package_record=package_record,
            console_scripts=console_scripts,
            about=about,
        )


# The keys are pypi names
# conda_pupae.dist_repodata.grayskull_pypi_mapping['zope-hookable']
# {
#     "pypi_name": "zope-hookable",
#     "conda_name": "zope.hookable",
#     "import_name": "zope.hookable",
#     "mapping_source": "regro-bot",
# }
grayskull_pypi_mapping = json.loads(
    pkgutil.get_data("conda_pupae", "grayskull_pypi_mapping.json") or "{}"
)


def requires_to_conda(requires: list[str] | None):
    from collections import defaultdict

    extras: dict[str, list[str]] = defaultdict(list)
    requirements = []
    for requirement in [Requirement(dep) for dep in requires or []]:
        # if requirement.marker and not requirement.marker.evaluate():
        #     # excluded by environment marker
        #     # see also marker evaluation according to given sys.executable
        #     continue
        name = canonicalize_name(requirement.name)
        requirement.name = pypi_to_conda_name(name)
        as_conda = f"{requirement.name} {requirement.specifier}"

        if (marker := requirement.marker) is not None:
            # for var, _, value in marker._markers:
            for mark in marker._markers:
                if isinstance(mark, tuple):
                    var, _, value = mark
                    if str(var) == "extra":
                        extras[str(value)].append(as_conda)
        else:
            requirements.append(f"{requirement.name} {requirement.specifier}".strip())

    return requirements, extras

    # if there is a url or extras= here we have extra work, may need to
    # yield Requirement not str
    # sorted(packaging.requirements.SpecifierSet("<5,>3")._specs, key=lambda x: x.version)
    # or just sorted lexicographically in str(SpecifierSet)
    # yield f"{requirement.name} {requirement.specifier}"


def pypi_to_conda_name(name):
    return grayskull_pypi_mapping.get(
        name,
        {
            "pypi_name": name,
            "conda_name": name,
            "import_name": None,
            "mapping_source": None,
        },
    )["conda_name"]


if __name__ == "__main__":  # pragma: no cover
    base = sys.argv[1]
    for path in Path(base).glob("*.dist-info"):
        print(CondaMetadata.from_distribution(PathDistribution(path)))
