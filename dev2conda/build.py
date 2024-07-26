import os
import tarfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from conda_package_streaming.transmute import transmute_stream

from .conda_build_utils import PathType, sha256_checksum


def filter(tarinfo):
    """
    Anonymize uid/gid; exclude .git directories.
    """
    if tarinfo.name.endswith(".git"):
        return None
    tarinfo.uid = tarinfo.gid = 0
    tarinfo.uname = tarinfo.gname = "root"
    return tarinfo


def create(source, destination, file_id, filter=filter):
    """
    Copy files from source into a .conda at destination.
    """
    with builder(destination, file_id) as tar:
        tar.add(source, "", filter=filter)

    return destination / (file_id + ".conda")


@contextmanager
def builder(
    destination, file_id, is_info=lambda filename: filename.startswith("info/")
):
    """
    Yield TarFile object for adding files, then transmute to "{destination}/{file_id}.conda"
    """
    # Stream through a pipe instead of collecting all data in a temporary
    # tarfile. Underlying transmute_stream collects data into separate pkg, info
    # tar to be able to send complete size to zstd, so this strategy avoids one
    # temporary file but not all of them. Compare to conda-package-handling 2.3
    # which uses less temporary space but reads every input file twice; once to
    # count the size and a second time to stream into a zstd compressor.
    r, w = os.pipe()
    with open(r, mode="rb") as reader, open(w, mode="wb") as writer:

        def transmute_thread():
            with tarfile.open(fileobj=reader, mode="r|") as tar:
                transmute_stream(
                    file_id,
                    destination,
                    package_stream=((tar, entry) for entry in tar),
                    is_info=is_info,
                )

        t = threading.Thread(target=transmute_thread)
        t.start()

        with tarfile.open(fileobj=writer, mode="w|") as tar:
            yield tar

        t.join()


def index_json(
    name, version="0.0.0", build="0", build_number=0, subdir="noarch", depends=()
):
    return {
        "build": build,
        "build_number": build_number,
        "depends": list(depends),
        "license": "",
        "license_family": "",
        "name": name,
        "subdir": subdir,
        "timestamp": time.time_ns() // 1000000,
        "version": version,
    }


# see conda_build.build.build_info_files_json_v1
def paths_json(base: Path | str):
    """
    Build simple paths.json with only 'hardlink' or 'symlink' types.
    """
    base = str(base)

    if not base.endswith(os.sep):
        base = base + os.sep

    return {
        "paths": sorted(_paths(base, base), key=lambda entry: entry["_path"]),
        "paths_version": 1,
    }


def _paths(base, path, filter=lambda x: x.name != ".git"):
    for entry in os.scandir(path):
        # TODO convert \\ to /
        relative_path = entry.path[len(base) :]
        if relative_path == "info" or not filter(entry):
            continue
        if entry.is_dir():
            yield from _paths(base, entry.path, filter=filter)
        elif entry.is_file() or entry.is_symlink():
            try:
                st_size = entry.stat().st_size
            except FileNotFoundError:
                st_size = 0  # symlink to nowhere
            yield {
                "_path": relative_path,
                "path_type": str(
                    PathType.softlink if entry.is_symlink() else PathType.hardlink
                ),
                "sha256": sha256_checksum(entry.path, entry),
                "size_in_bytes": st_size,
            }
        else:
            print("Not regular file", entry)
            # will Python's tarfile add pipes, device nodes to the archive?
