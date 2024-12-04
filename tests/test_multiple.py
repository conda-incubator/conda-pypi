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

from conda.models.match_spec import MatchSpec

from conda_pupa.build import build_conda
from conda_pupa.downloader import download_pypi_pip
from conda_pupa.index import update_index

REPO = pathlib.Path(__file__).parents[1] / "synthetic_repo"


def list_envs():
    output = subprocess.run(
        f"{os.environ['CONDA_EXE']} info --envs --json".split(),
        capture_output=True,
        check=True,
    )
    env_info = json.loads(output.stdout)
    return env_info


def create_test_env(name):
    """
    Create named environment if it does not exist.
    """
    envs = list_envs()
    if not any((e.endswith(f"{os.sep}{name}") for e in envs["envs"])):
        subprocess.run(
            [os.environ["CONDA_EXE"], "create", "-n", name, "-y", "python 3.12"],
            check=True,
            encoding="utf-8",
        )
    return envs


def test_multiple(tmp_path):
    """
    Install multiple only-available-from-pypi dependencies into an environment.
    """
    TARGET_ENV = "pupa-target"
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

    create_test_env(TARGET_ENV)

    TARGET_DEP = "twine==5.1.1"

    # if we asked for pypi_simple, it would get normalized to pypi-simple and we
    # would get confused.
    TARGET_DEP = "unearth"

    # XXX httpcore=1 needs to be converted to  httpcore==1 e.g.

    converted = set()
    fetched_packages = set()
    missing_packages = set()
    while len(fetched_packages) < MAX_TRIES:
        try:
            command = [
                os.environ["CONDA_EXE"],
                "install",
                "-n",
                TARGET_ENV,
                TARGET_DEP,
                "--json",
                "--override-channels",
                "-c",
                REPO,
            ]
            subprocess.run(
                command,
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

    subprocess.run([os.environ["CONDA_EXE"], "list", "-n", TARGET_ENV])


NOTHING_PROVIDES_RE = re.compile(r"nothing provides (.*) needed by")


def parse_libmamba_error(message: str):
    """
    Parse missing packages out of LibMambaUnsatisfiableError message.
    """
    for line in message.splitlines():
        if match := NOTHING_PROVIDES_RE.search(line):
            yield match.group(1)
