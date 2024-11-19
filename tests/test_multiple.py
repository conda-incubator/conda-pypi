"""
Install a tree of wheel dependencies into a different conda environment.
"""

import json
import os
import pathlib
import pprint
import re
import subprocess
import sys
from pathlib import Path

from conda.models.match_spec import MatchSpec
from pypi_simple import PyPISimple

from conda_pupa.editable import build_conda
from conda_pupa.index import update_index
from conda_pupa.translate import conda_to_requires

TARGET_ENV = "pupa-target"

REPO = pathlib.Path(__file__).parents[1] / "synthetic_repo"


def list_envs():
    output = subprocess.run(
        f"{os.environ['CONDA_EXE']} info --envs --json".split(),
        capture_output=True,
        check=True,
    )
    env_info = json.loads(output.stdout)
    return env_info


def test_multiple(tmp_path):
    """
    Install multiple only-available-from-pypi dependencies into an environment.
    """
    MAX_TRIES = 32

    # defeat local cache. This test also uses a persistent TARGET_ENV; delete
    # manually if done before expected.
    CONDA_PKGS_DIRS = tmp_path / "conda-pkgs"
    CONDA_PKGS_DIRS.mkdir()
    env = os.environ.copy()
    env["CONDA_PKGS_DIRS"] = str(CONDA_PKGS_DIRS)

    WHEEL_DIR = tmp_path / "wheels"
    WHEEL_DIR.mkdir(exist_ok=True)

    REPO.mkdir(parents=True, exist_ok=True)

    # ensure index even if it starts empty
    update_index(REPO)

    envs = list_envs()
    if not any((e.endswith(f"{os.sep}{TARGET_ENV}") for e in envs["envs"])):
        subprocess.run(
            f"{os.environ['CONDA_EXE']} create -n {TARGET_ENV} -y python".split(),
            check=True,
            encoding="utf-8",
        )

    TARGET_DEP = "twine==5.1.1"

    converted = set()
    fetched_packages = set()
    missing_packages = set()
    while len(fetched_packages) < MAX_TRIES:
        try:
            command = f"{os.environ['CONDA_EXE']} install -n {TARGET_ENV} {TARGET_DEP} --json --override-channels -c {REPO}"
            subprocess.run(
                command.split(),
                check=True,
                capture_output=True,
                encoding="utf-8",
                env=env,
            )
            print("SUCCESS:", command)
            break

        except subprocess.CalledProcessError as result:
            result_json = json.loads(result.stdout)

            print("Grab more packages", result_json["message"])

            if result_json["exception_name"] == "PackagesNotFoundError":
                missing_packages.update(set(result_json["packages"]))

            elif result_json["exception_name"] == "LibMambaUnsatisfiableError":
                # libmamba will say "nothing provides pkginfo >=1.8.1 needed by
                # twine-5.1.1-0"

                # classic will say "The following specifications were found to be
                # incompatible with each other:\n\nOutput in format: Requested
                # package -> Available versions"
                missing_packages.update(
                    set(parse_libmamba_error(result_json["message"]))
                )

            else:
                raise

            for package in sorted(missing_packages - fetched_packages):
                download_pypi_pip(MatchSpec(package), WHEEL_DIR)

            for normal_wheel in WHEEL_DIR.glob("*.whl"):
                if normal_wheel in converted:
                    continue

                print("Convert", normal_wheel)

                build_path = tmp_path / normal_wheel.stem
                build_path.mkdir()

                try:
                    package_conda = build_conda(
                        normal_wheel,
                        build_path,
                        REPO / "noarch",  # XXX could be arch
                        sys.executable,
                        is_editable=False,
                    )
                    print("Conda at", package_conda)
                except FileExistsError:
                    print(
                        "Tried to convert wheel that is already conda-ized",
                        normal_wheel,
                    )

                converted.add(normal_wheel)

            # subprocess to avoid any buggy caching in update_index?
            # subprocess.run([sys.executable, "-m", "conda_index", REPO])
            update_index(REPO)

            fetched_packages.update(missing_packages)

    pprint.pprint(fetched_packages)

    subprocess.run(f"{os.environ['CONDA_EXE']} list -n {TARGET_ENV}".split())


NOTHING_PROVIDES_RE = re.compile(r"nothing provides (.*) needed by")


def parse_libmamba_error(message: str):
    """
    Parse missing packages out of LibMambaUnsatisfiableError message.
    """
    for line in message.splitlines():
        if match := NOTHING_PROVIDES_RE.search(line):
            yield match.group(1)


def download_pypi_pip(matchspec: MatchSpec, target_path: Path):
    """
    Prototype download wheel for missing package using pip.

    Complete implementation should match wheels based on target environment at
    least, directly use pypi API instead of pip.
    """
    requirement = conda_to_requires(matchspec)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--only-binary",
            ":all:",
            "-w",
            str(target_path),
            str(requirement),
        ],
        check=True,
    )


def download_pypi_nopip(matchspec: MatchSpec):
    """
    (What could become) lower level download wheel for missing package not using pip.

    Would not require pip to be installed in the target environment, for one.

    Complete implementation should match wheels based on target environment at
    least, directly use pypi API instead of pip.
    """
    # Code lifted from corpus.py
    with PyPISimple() as client:
        try:
            page = client.get_project_page(package.name)
        except pypi_simple.errors.NoSuchProjectError as e:
            print(package.name, e)
            return
        # TODO code to skip already-fetched projects
        for pkg in page.packages:
            if pkg.version != package.version:
                print(pkg.version, "!=", package.version)
                return
            if pkg.has_metadata is not None:
                print("Has metadata?", pkg.has_metadata)
                try:
                    src = client.get_package_metadata(pkg)
                except NoMetadataError:
                    print(f"{pkg.filename}: No metadata available")
                else:
                    print(pkg)
                    # avoid unique errors
                    session.execute(
                        pypi_metadata.delete().where(
                            pypi_metadata.c.filename == pkg.filename
                        )
                    )
                    session.execute(
                        pypi_metadata.insert().values(
                            filename=pkg.filename,
                            name=pkg.project,
                            version=pkg.version,
                            metadata=src,
                        )
                    )
            else:
                print(f"{pkg.filename}: No metadata available")
            print()
