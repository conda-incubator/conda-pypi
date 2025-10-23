import os

import pytest
from conda.cli.main import main_subshell


@pytest.mark.parametrize(
    "source, editable",
    [
        ("tests/packages/has-build-dep", False),
        ("tests/packages/has-build-dep", True),
    ],
)
def test_convert_writes_output(tmp_path, source, editable):
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    args = ["pypi", "convert", "--output-folder", str(out_dir)]
    if editable:
        args.append("-e")
    args.append(source)
    main_subshell(*args)

    files = list(out_dir.glob("*.conda"))
    assert files, f"No .conda artifacts found in {out_dir}"

    assert files[0].is_file()
    assert os.path.getsize(files[0]) > 0
