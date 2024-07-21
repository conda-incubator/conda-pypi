from pathlib import Path

from dev2conda.tarconda import create, index_json
import zipfile
import shutil
from subprocess import run
import sys
import json

here = Path(__file__).parent


def test_tarconda(tmp_path):
    create(here.parent, tmp_path)
    zf = zipfile.ZipFile(tmp_path / "someconda.conda", "r")
    assert zf.filelist[0].filename == "metadata.json"


def test_indexable(tmp_path):
    # tmp_path = Path("/tmp/test")
    # tmp_path.mkdir()
    dest = tmp_path / "somepackage"
    noarch = tmp_path / "noarch"
    noarch.mkdir()
    shutil.copytree(here.parent, dest, ignore=shutil.ignore_patterns(".git"))
    (dest / "info").mkdir()
    (dest / "info" / "index.json").write_text(json.dumps(index_json("somepackage")))

    create(dest, noarch)

    # can cause a circular import in requests if charset-normalizer but not chardet is installed
    run([sys.executable, "-m", "conda_index", str(tmp_path)], check=True)
    repodata = json.loads((noarch / "repodata.json").read_text())
    assert repodata["packages.conda"]
