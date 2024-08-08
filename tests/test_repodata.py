"""
Test functions for transforming repodata.
"""

from conda_pupae.dist_repodata import FileDistribution


def test_file_distribution():
    dist = FileDistribution(
        """\
Metadata-Version: 2.1
Name: conda_pupae
Version: 0.0.1
"""
    )
    metadata = dist.read_text("METADATA") or ""
    assert "conda_pupae" in metadata
    assert dist.read_text("missing") is None
    assert dist.locate_file("always None") is None
