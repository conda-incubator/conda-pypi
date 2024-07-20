from pathlib import Path

from dev2conda.tarconda import create
import zipfile

here = Path(__file__).parent


def test_tarconda(tmp_path):
    create(here.parent, tmp_path)
    zf = zipfile.ZipFile(tmp_path / "someconda.conda", "r")
    assert zf.filelist[0].filename == "metadata.json"
