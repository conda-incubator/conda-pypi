import pathlib

import pytest

import conda_pupa.synth


def test_synth():
    # TODO too much network access
    conda_pupa.synth.create_api("config.yaml", "synthetic_repo", True)
    assert (
        pathlib.Path(__file__).parents[1]
        / "synthetic_repo"
        / "noarch"
        / "repodata.json"
    ).exists()


def test_extract_version_of_project():
    class project_page:
        packages = []

    version, package, url = conda_pupa.synth.extract_version_of_project(
        project_page,  # type: ignore
        version="",
        download=False,
        download_dir="",
    )
    assert version == "0.0.0"
    assert isinstance(package, conda_pupa.synth.Package)
    assert isinstance(url, str)


def test_bad_config(tmp_path):
    """
    Exercise error handling path.
    """

    config = tmp_path / "config.yaml"
    config.write_text("")
    with pytest.raises(AttributeError):
        conda_pupa.synth.create_api(config, "synthetic_repo", True)
