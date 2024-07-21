import tarfile
import tempfile
from pathlib import Path
import time

from conda_package_streaming.transmute import transmute_stream


def create(source, destination):
    """
    Copy files from source into a .conda at destination.
    """

    def filter(tarinfo):
        if tarinfo.name.endswith(".git"):
            return None
        tarinfo.uid = tarinfo.gid = 0
        tarinfo.uname = tarinfo.gname = "root"
        return tarinfo

    with tempfile.TemporaryDirectory("tarconda") as tempdir:
        with tarfile.TarFile(Path(tempdir, "tarconda.tar"), "w") as tar:
            tar.add(source, "", filter=filter)

        with tarfile.TarFile(Path(tempdir, "tarconda.tar"), "r") as tar:
            transmute_stream(
                "someconda", destination, package_stream=((tar, entry) for entry in tar)
            )


def index_json(name, version="0.0.0", subdir="noarch", depends=()):
    return {
        "build": "0",
        "build_number": 0,
        "depends": list(depends),
        "license": "",
        "license_family": "",
        "name": name,
        "subdir": subdir,
        "timestamp": time.time_ns() / 1000000,
        "version": version,
    }
