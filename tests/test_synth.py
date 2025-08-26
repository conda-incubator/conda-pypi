import pathlib

import pytest

import conda_pypi.synth


def test_synth():
    # TODO too much network access
    config_path = pathlib.Path(__file__).parents[1] / "config.yaml"
    repo_path = "synthetic_repo"

    if not config_path.exists():
        pytest.skip(f"Config file not found at {config_path}")

    try:
        conda_pypi.synth.create_api(str(config_path), repo_path, True)
    except Exception as e:
        pytest.fail(f"create_api failed: {e}")

    repodata_file = pathlib.Path(__file__).parents[1] / repo_path / "noarch" / "repodata.json"
    assert repodata_file.exists(), f"repodata.json not found at {repodata_file}"


def test_extract_version_of_project():
    class project_page:
        packages = []

    version, package, url = conda_pypi.synth.extract_version_of_project(
        project_page,  # type: ignore
        version="",
        download=False,
        download_dir="",
    )
    assert version == "0.0.0"
    assert isinstance(package, conda_pypi.synth.Package)
    assert isinstance(url, str)


def test_bad_config(tmp_path):
    """
    Exercise error handling path.
    """

    config = tmp_path / "config.yaml"
    config.write_text("")
    with pytest.raises(AttributeError):
        conda_pypi.synth.create_api(config, "synthetic_repo", True)
