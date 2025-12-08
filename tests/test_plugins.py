from conda.testing.fixtures import CondaCLIFixture, TmpEnvFixture
from pytest_mock import MockerFixture
from conda_pypi.pre_command import extract_whl_or_tarball
from conda_pypi.pre_command.extract_whl import extract_whl_as_conda_pkg
from conda_pypi.whl import add_whl_support
import pytest
from pathlib import Path
import conda.core.subdir_data


WHL_HTTP_URL = "https://files.pythonhosted.org/packages/45/7f/0e961cf3908bc4c1c3e027de2794f867c6c89fb4916fc7dba295a0e80a2d/boltons-25.0.0-py3-none-any.whl"
CONDA_URL = "https://repo.anaconda.com/pkgs/main/osx-arm64/boltons-25.0.0-py314hca03da5_0.conda"


@pytest.mark.parametrize(
    "package,call_count",
    [
        pytest.param(WHL_HTTP_URL, 1, id=".whl url"),
        pytest.param("{file}", 1, id=".whl file"),
        pytest.param("file:///{file}", 1, id=".whl file url"),
        pytest.param(CONDA_URL, 0, id=".conda url"),
    ],
)
def test_extract_whl_as_conda_called(
    tmp_env: TmpEnvFixture,
    conda_cli: CondaCLIFixture,
    mocker: MockerFixture,
    pypi_demo_package_wheel_path: Path,
    tmp_pkgs_dir: Path,  # use empty package cache directory
    tmp_path: Path,
    package: str,
    call_count: int,
):
    package = package.format(file=pypi_demo_package_wheel_path)
    with tmp_env() as prefix:
        # mock python installed in prefix
        mocker.patch(
            "conda.core.link.UnlinkLinkTransaction._get_python_info",
            return_value=("3.10", str(tmp_path)),
        )

        # spy on monkeypatches
        spy_extract_whl_as_conda_pkg = mocker.spy(
            extract_whl_or_tarball.extract_whl, "extract_whl_as_conda_pkg"
        )

        # install package
        conda_cli("install", f"--prefix={prefix}", package)

        # wheel extraction only happens for .whl
        assert spy_extract_whl_as_conda_pkg.call_count == call_count


def test_extract_whl_as_conda_pkg(
    pypi_demo_package_wheel_path: Path,
    tmp_path: Path,
):
    extract_whl_as_conda_pkg(pypi_demo_package_wheel_path, tmp_path)


def test_packages_whl_reading(mocker: MockerFixture):
    """
    Test that conda can read packages.whl from server-hosted repodata.

    This tests the patch in whl.py that merges packages.whl into packages
    when conda reads repodata from a server channel.
    """
    mocker.patch.object(
        conda.core.subdir_data.SubdirData,
        "_process_raw_repodata",
        side_effect=lambda self, repodata, state=None: repodata,
    )

    add_whl_support()

    repodata = {
        "packages": {},
        "packages.whl": {
            "demo_package-0.1.0-pypi_0.whl": {
                "name": "demo_package",
                "version": "0.1.0",
                "fn": "demo_package-0.1.0-pypi_0.whl",
            }
        },
    }

    result = conda.core.subdir_data.SubdirData._process_raw_repodata(
        mocker.Mock(), repodata.copy()
    )

    assert "demo_package-0.1.0-pypi_0.whl" in result["packages"]
    assert result["packages"]["demo_package-0.1.0-pypi_0.whl"]["name"] == "demo_package"
