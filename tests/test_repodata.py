"""
Test functions for transforming repodata.
"""

from conda_pypi.translate import FileDistribution, MatchSpec, conda_to_requires


def test_file_distribution():
    dist = FileDistribution(
        """\
Metadata-Version: 2.1
Name: conda_pypi
Version: 0.0.1
"""
    )
    metadata = dist.read_text("METADATA") or ""
    assert "conda_pypi" in metadata
    assert dist.read_text("missing") is None
    assert dist.locate_file("always None") is None


def test_translate_twine():
    requirement = conda_to_requires(MatchSpec("twine==6.0.0"))
    assert requirement.name == "twine"
