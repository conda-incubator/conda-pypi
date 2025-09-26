from pathlib import Path
import json

from conda_package_streaming import package_streaming

from conda.testing.fixtures import TmpEnvFixture
from conda.common.path import get_python_short_path

from conda_pypi.build import build_conda


def test_build_conda_package(
    tmp_env: TmpEnvFixture,
    pypi_demo_package_wheel_path: Path,
    tmp_path: Path,
):
    build_path = tmp_path / "build"
    build_path.mkdir()

    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    target_package_path = repo_path / "demo-package-0.1.0-pypi_0.conda"

    with tmp_env("python=3.12", "pip") as prefix:
        conda_package_path = build_conda(
            pypi_demo_package_wheel_path,
            build_path,
            repo_path,
            Path(prefix, get_python_short_path()),
            is_editable=False,
        )
        assert conda_package_path is not None

        # Get a list of all the files in the package
        included_package_paths = [
            mm.name for _, mm in package_streaming.stream_conda_component(target_package_path)
        ]

        # Get the list of all the paths listed in the paths.json file
        for tar, member in package_streaming.stream_conda_info(target_package_path):
            if member.name == "info/paths.json":
                paths_json = json.load(tar.extractfile(member))
                paths_json_paths = [path.get("_path") for path in paths_json.get("paths")]
                break

        # Ensure that the path.json file matches the packages up paths
        for path in paths_json_paths:
            assert path in included_package_paths
