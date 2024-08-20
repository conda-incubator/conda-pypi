import os
import time
from pathlib import Path

from .conda_build_utils import PathType, sha256_checksum
from .create import conda_builder


def filter(tarinfo):
    """
    Anonymize uid/gid; exclude .git directories.
    """
    if tarinfo.name.endswith(".git"):
        return None
    tarinfo.uid = tarinfo.gid = 0
    tarinfo.uname = tarinfo.gname = ""
    return tarinfo


def create(source, destination, file_id, filter=filter):
    """
    Copy files from source into a .conda at destination.
    """
    with conda_builder(file_id, destination) as tar:
        tar.add(source, "", filter=filter)

    return destination / (file_id + ".conda")


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
