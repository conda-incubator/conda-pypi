import hashlib
import json
import os
from pathlib import Path

from conda.cli.main import main_subshell

from conda_pupa.build import filter, paths_json
from conda_pupa.conda_build_utils import PathType, sha256_checksum
from conda_pupa.create import conda_builder
from conda_pupa.index import update_index
from conda_pupa.translate import PackageRecord

here = Path(__file__).parent


def test_indexable(tmp_path):
    """
    Create a .conda from scratch; index and install the package.
    """
    noarch = tmp_path / "noarch"
    noarch.mkdir()

    NAME = "somepackage"
    VERSION = "1.0"

    record = PackageRecord(
        name=NAME, version=VERSION, subdir="noarch", depends=[], extras={}
    )
    dest = tmp_path / record.stem
    dest.mkdir()

    (dest / "packaged.txt").write_text("packaged file")
    (dest / "info").mkdir()
    (dest / "info" / "index.json").write_text(json.dumps(record.to_index_json()))

    paths = paths_json(dest)
    (dest / "info" / "paths.json").write_text(json.dumps(paths))

    with conda_builder(record.stem, noarch) as tar:
        tar.add(dest, "", filter=filter)

    update_index(tmp_path)

    repodata = json.loads((noarch / "repodata.json").read_text())
    assert repodata["packages.conda"]

    # name, version, build = dist_str.rsplit("-", 2) must be named like this
    dest_package = noarch / f"{record.stem}.conda"
    assert dest_package.exists()

    main_subshell(
        "create",
        "--prefix",
        str(tmp_path / "env"),
        "--channel",
        f"file://{tmp_path}",
        "--override-channels",
        "-y",
        "somepackage",
    )

    conda_meta = json.loads(
        (tmp_path / "env" / "conda-meta" / f"{record.stem}.json").read_text()
    )
    assert len(conda_meta["files"])


def test_path_type():
    assert PathType.hardlink.__json__() == str(PathType.hardlink)


def test_checksum(tmp_path):
    (tmp_path / "nowhere").symlink_to(tmp_path / "missing")
    assert sha256_checksum(tmp_path / "nowhere") == hashlib.sha256().hexdigest()
    os.mkfifo(tmp_path / "fifo")
    assert sha256_checksum(tmp_path / "fifo") is None

    paths = paths_json(tmp_path)
    assert len(paths["paths"])
