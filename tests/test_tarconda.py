import hashlib
import json
import os
import shutil
import zipfile
from pathlib import Path

from conda.cli.main import main_subshell
from conda_package_streaming.conda_fmt import conda_builder

from conda_pupae.build import create, filter, index_json, paths_json
from conda_pupae.conda_build_utils import PathType, sha256_checksum
from conda_pupae.index import update_index

here = Path(__file__).parent


def test_tarconda(tmp_path):
    create(here.parent, tmp_path, "someconda")
    zf = zipfile.ZipFile(tmp_path / "someconda.conda", "r")
    assert zf.filelist[0].filename == "metadata.json"


def test_indexable(tmp_path):
    noarch = tmp_path / "noarch"
    noarch.mkdir()

    NAME = "somepackage"
    VERSION = "1.0"

    record = index_json(NAME, VERSION)

    file_id = f"{record['name']}-{record['version']}-{record['build']}"

    dest = tmp_path / file_id

    shutil.copytree(here.parent, dest, ignore=shutil.ignore_patterns(".git"))

    (dest / "info").mkdir()
    (dest / "info" / "index.json").write_text(json.dumps(record))

    paths = paths_json(dest)

    (dest / "info" / "paths.json").write_text(json.dumps(paths))

    with conda_builder(file_id, noarch) as tar:
        tar.add(dest, "", filter=filter)

    update_index(tmp_path)

    repodata = json.loads((noarch / "repodata.json").read_text())
    assert repodata["packages.conda"]

    # name, version, build = dist_str.rsplit("-", 2) must be named like this
    dest_package = noarch / f"{file_id}.conda"
    assert dest_package.exists()

    main_subshell("create", "--prefix", str(tmp_path / "env"), str(dest_package))

    # in conda-meta
    example_conda_meta = {
        "build": "0",
        "build_number": 0,
        "channel": "file:///tmp/pytest-of-dholth/pytest-50/test_indexable0/noarch",
        "constrains": [],
        "depends": [],
        "extracted_package_dir": "/home/dholth/miniconda3/pkgs/somepackage-1.0-0",
        "files": [],  # will contain failes
        "fn": "somepackage-1.0-0.conda",
        "license": "",
        "license_family": "",
        "link": {"source": "/home/dholth/miniconda3/pkgs/somepackage-1.0-0", "type": 1},
        "md5": "c551ede58a0344516e1b803de10ff5c8",
        "name": "somepackage",
        "package_tarball_full_path": "/home/dholth/miniconda3/pkgs/somepackage-1.0-0.conda",
        "paths_data": {
            "paths": [],
            "paths_version": 1,
        },  # duplicates "files" list? plus checksums
        "requested_spec": "test_indexable0/noarch::somepackage==1.0=0",
        "sha256": "ba7741b7ce1470357397f6f8f4d0467be8d4162006e5a87e276c28d3b2cfbc14",
        "size": 79824,
        "subdir": "noarch",
        "timestamp": 1721655445630,
        "url": "file:///tmp/pytest-of-dholth/pytest-50/test_indexable0/noarch/somepackage-1.0-0.conda",
        "version": "1.0",
    }

    conda_meta = json.loads(
        (tmp_path / "env" / "conda-meta" / f"{file_id}.json").read_text()
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
