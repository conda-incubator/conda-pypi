"""
Build a Python project into an editable wheel, convert to a .conda and install
the .conda.
"""

import itertools
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from conda.cli.main import main_subshell

from build import ProjectBuilder, check_dependency

from . import build
from .dist_repodata import fetch_data


def normalize(name):
    # pypa package name normalization
    return re.sub(r"[-_.]+", "-", name).lower()


def json_dumps(object):
    """
    Consistent json formatting.
    """
    return json.dumps(object, indent=2, sort_keys=True)


def flatten(iterable):
    return [*itertools.chain(*iterable)]


def ensure_requirements(requirements):
    # XXX we need to parse environment markers e.g. "tomli;
    # python_version < '3.11'" see pyproject-hooks
    # https://packaging.pypa.io/en/stable/markers.html#markers
    if requirements:
        main_subshell("install", *(normalize(r) for r in requirements))


def build_pypa(path: Path, output_path, python_executable):
    builder = ProjectBuilder(path, python_executable=python_executable)

    build_system_requires = builder.build_system_requires
    missing = {u for d in build_system_requires for u in check_dependency(d)}
    print("Installing requirements for build system:", missing)
    # does flatten() work for a deeper dependency chain?
    ensure_requirements(flatten(missing))

    editable_requirements = builder.check_dependencies("editable")
    print("Additional requirements for build_editable:", editable_requirements)
    ensure_requirements(flatten(editable_requirements))

    editable_file = builder.build("editable", output_path)
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
    metadata = fetch_data(dist_info)

    record = build.index_json(
        metadata["name"],
        metadata["version"],
        subdir="noarch",
        depends=metadata["requirements"]["run"],
    )
    record["noarch"] = "python"

    # XXX set build string as hash of pypa metadata so that conda can re-install
    # when project gains new entry-points, dependencies?

    file_id = f"{record['name']}-{record['version']}-{record['build']}"

    (build_path / "info").mkdir()
    (build_path / "info" / "index.json").write_text(json_dumps(record))

    paths = build.paths_json(build_path)

    (build_path / "info" / "paths.json").write_text(json_dumps(paths))

    with build.builder(output_path, file_id) as tar:
        tar.add(build_path, "", filter=build.filter)

    return output_path / f"{file_id}.conda"


def editable(project):
    with tempfile.TemporaryDirectory(prefix="conda", delete=False) as output_path:
        output_path = Path(output_path)
        editable_wheel = build_pypa(Path(project), output_path, sys.executable)
        editable_conda = build_conda(editable_wheel, output_path, sys.executable)
        print("Editable conda at", editable_conda)


if __name__ == "__main__":  # pragma: no cover
    editable(sys.argv[1])
