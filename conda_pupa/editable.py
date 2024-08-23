"""
Build a Python project into an editable wheel, convert to a .conda and install
the .conda.
"""

import itertools
import json
import subprocess
import sys
import tempfile
from importlib.metadata import PathDistribution
from pathlib import Path

from conda.cli.main import main_subshell
from packaging.utils import canonicalize_name

from build import ProjectBuilder, check_dependency

from . import build
from .create import conda_builder
from .translate import CondaMetadata, requires_to_conda


def normalize(name):
    return canonicalize_name(name)


def json_dumps(object):
    """
    Consistent json formatting.
    """
    return json.dumps(object, indent=2, sort_keys=True)


def flatten(iterable):
    return [*itertools.chain(*iterable)]


def ensure_requirements(requirements):
    if requirements:
        conda_requirements, _ = requires_to_conda(requirements)
        # -y may be appropriate during tests only
        main_subshell("install", "-y", *conda_requirements)


def build_pypa(path: Path, output_path, python_executable, distribution="editable"):
    """
    Args:
        distribution: "editable" or "wheel"
    """
    builder = ProjectBuilder(path, python_executable=python_executable)

    build_system_requires = builder.build_system_requires
    missing = {u for d in build_system_requires for u in check_dependency(d)}
    print("Installing requirements for build system:", missing)
    # does flatten() work for a deeper dependency chain?
    ensure_requirements(flatten(missing))

    requirements = builder.check_dependencies(distribution)
    print(f"Additional requirements for {distribution}:", requirements)
    ensure_requirements(flatten(requirements))

    editable_file = builder.build(distribution, output_path)
    print("The wheel is at", editable_file)

    return editable_file


def build_conda(whl, output_path: Path, python_executable):
    build_path = output_path / "build"
    build_path.mkdir()

    # could we find the local channel for conda-build, drop our new package
    # there and have it automatically be found
    command = [
        python_executable,
        "-m",
        "pip",
        "install",
        "--no-deps",
        "--target",
        str(build_path / "site-packages"),
        whl,
    ]
    subprocess.run(command, check=True)
    print("Installed to", build_path)

    dist_info = next((build_path / "site-packages").glob("*.dist-info"))
    metadata = CondaMetadata.from_distribution(PathDistribution(dist_info))
    record = metadata.package_record.to_index_json()
    # XXX set build string as hash of pypa metadata so that conda can re-install
    # when project gains new entry-points, dependencies?

    file_id = f"{record['name']}-{record['version']}-{record['build']}"

    (build_path / "info").mkdir()
    (build_path / "info" / "index.json").write_text(json_dumps(record))

    paths = build.paths_json(build_path)

    (build_path / "info" / "paths.json").write_text(json_dumps(paths))

    with conda_builder(file_id, output_path) as tar:
        tar.add(build_path, "", filter=build.filter)

    return output_path / f"{file_id}.conda"


def editable(project, distribution="editable"):
    with tempfile.TemporaryDirectory(prefix="conda", delete=False) as output_path:
        output_path = Path(output_path)
        normal_wheel = build_pypa(
            Path(project), output_path, sys.executable, distribution=distribution
        )
        package_conda = build_conda(normal_wheel, output_path, sys.executable)
        print("Conda at", package_conda)


if __name__ == "__main__":  # pragma: no cover
    editable(sys.argv[1])
