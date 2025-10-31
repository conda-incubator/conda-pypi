import codecs
import json
import os
from os import PathLike

from installer.records import RecordEntry, Hash
from installer.sources import WheelFile
from installer.destinations import WheelDestination
from installer.utils import Scheme

import installer.utils

from typing import Literal, BinaryIO, Iterable, Tuple


SUPPORTED_SCEMES: Tuple[Scheme] = ("platlib", "purelib")


# inline version of
# from conda.gateways.disk.create import write_as_json_to_file
def write_as_json_to_file(file_path, obj):
    with codecs.open(file_path, mode="wb", encoding="utf-8") as fo:
        json_str = json.dumps(
            obj,
            indent=2,
            sort_keys=True,
            separators=(",", ": "),
        )
        fo.write(json_str)


class MyWheelDestination(WheelDestination):
    def __init__(self, target_full_path: str) -> None:
        self.target_full_path = target_full_path
        self.sp_dir = os.path.join(target_full_path, "site-packages")
        self.entry_points = []

    def write_script(
        self, name: str, module: str, attr: str, section: Literal["console"] | Literal["gui"]
    ) -> RecordEntry:
        # TODO check if console/gui
        entry_point = f"{name} = {module}:{attr}"
        self.entry_points.append(entry_point)
        return RecordEntry(
            path="../../../bin/{name}",
            hash_=None,
            size=None,
        )

    def write_file(
        self, scheme: Scheme, path: str | PathLike[str], stream: BinaryIO, is_executable: bool
    ) -> RecordEntry:
        if scheme not in SUPPORTED_SCEMES:
            raise ValueError(f"Unsupported scheme: {scheme}")

        path = os.fspath(path)
        dest_path = os.path.join(self.sp_dir, path)

        parent_folder = os.path.dirname(dest_path)
        if not os.path.exists(parent_folder):
            os.makedirs(parent_folder)

        # print(f"Writing {dest_path} from {source}")
        with open(dest_path, "wb") as dest:
            hash_, size = installer.utils.copyfileobj_with_hashing(
                source=stream,
                dest=dest,
                hash_algorithm="sha256",
            )

        if is_executable:
            installer.utils.make_file_executable(dest_path)

        return RecordEntry(
            path=path,
            hash_=Hash("sha256", hash_),
            size=size,
        )

    def _create_conda_metadata(self, records: Iterable[Tuple[Scheme, RecordEntry]]) -> None:
        os.makedirs(os.path.join(self.target_full_path, "info"), exist_ok=True)
        # link.json
        link_json_data = {
            "noarch": {
                "type": "python",
            },
            "package_metadata_version": 1,
        }
        if self.entry_points:
            link_json_data["noarch"]["entry_points"] = self.entry_points
        link_json_path = os.path.join(self.target_full_path, "info", "link.json")
        write_as_json_to_file(link_json_path, link_json_data)

        # paths.json
        paths = []
        for _, record in records:
            if record.path.startswith(".."):
                # entry point
                continue
            path = {
                "_path": f"site-packages/{record.path}",
                "path_type": "hardlink",
                "sha256": record.hash_.value,
                "size_in_bytes": record.size,
            }
            paths.append(path)
        paths_json_data = {
            "paths": paths,
            "paths_version": 1,
        }
        paths_json_path = os.path.join(self.target_full_path, "info", "paths.json")
        write_as_json_to_file(paths_json_path, paths_json_data)

        # index.json
        # index.json file is empty, the actual index metadata comes from repodata
        index_json_data = {}
        index_json_path = os.path.join(self.target_full_path, "info", "index.json")
        write_as_json_to_file(index_json_path, index_json_data)

    def finalize_installation(
        self, scheme: Scheme, record_file_path: str, records: Iterable[Tuple[Scheme, RecordEntry]]
    ) -> None:
        record_list = list(records)
        with installer.utils.construct_record_file(record_list, lambda x: None) as record_stream:
            dest_path = os.path.join(self.sp_dir, record_file_path)
            with open(dest_path, "wb") as dest:
                hash_, size = installer.utils.copyfileobj_with_hashing(
                    record_stream, dest, "sha256"
                )
                record_file_record = RecordEntry(
                    path=record_file_path,
                    hash_=Hash("sha256", hash_),
                    size=size,
                )
        record_list[-1] = ("purelib", record_file_record)
        self._create_conda_metadata(record_list)
        return


def extract_whl_as_conda_pkg(whl_full_path: str, target_full_path: str):
    destination = MyWheelDestination(target_full_path)
    additional_metadata = {"INSTALLER": b"conda-via-whl"}
    with WheelFile.open(whl_full_path) as source:
        installer.install(
            source=source,
            destination=destination,
            additional_metadata=additional_metadata,
        )


if __name__ == "__main__":
    extract_whl_as_conda_pkg(
        "./imagesize-1.4.1-py2.py3-none-any.whl",
        "./unpack",
    )
