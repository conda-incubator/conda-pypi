from pathlib import Path

from conda_pupa.editable import editable, normalize


def test_editable():
    editable(Path(__file__).parents[1])


def test_normalize():
    assert normalize("flit_core") == "flit-core"
