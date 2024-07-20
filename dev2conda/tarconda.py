import tarfile
import tempfile
from pathlib import Path

from conda_package_streaming.transmute import transmute_stream


def create(source, destination):
    """
    Copy files from source into a .conda at destination.
    """

    def filter(tarinfo):
        if tarinfo.name.endswith(".git"):
            return None
        return tarinfo

    with tempfile.TemporaryDirectory("tarconda") as tempdir:
        with tarfile.TarFile(Path(tempdir, "tarconda.tar"), "w") as tar:
            tar.add(source, filter=filter)

        with tarfile.TarFile(Path(tempdir, "tarconda.tar"), "r") as tar:
            transmute_stream(
                "someconda", destination, package_stream=((tar, entry) for entry in tar)
            )
