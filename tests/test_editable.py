import subprocess
from pathlib import Path

import pytest
from packaging.requirements import InvalidRequirement

import build
from conda_pupa.build import ensure_requirements, filter
from conda_pupa.build import pypa_to_conda


def test_editable(tmp_path):
    pypa_to_conda(
        Path(__file__).parents[1], output_path=tmp_path, distribution="editable"
    )


def pypa_build_packages():
    """
    Test packages from pypa/build repository.

    (Clone pypa/build into tests/)
    """
    here = Path(__file__).parent
    return list(p.name for p in Path(here, "build", "tests", "packages").glob("*"))


@pytest.fixture
def package_path():
    here = Path(__file__).parent
    return Path(here, "build", "tests", "packages")


@pytest.mark.parametrize("package", pypa_build_packages())
def test_build_wheel(package, package_path, tmp_path):
    # Some of these will not contain the editable hook; need to test building
    # regular wheels also. Some will require a "yes" for conda install
    # dependencies. Some are designed to fail.
    xfail = [
        "test-bad-backend",
        "test-bad-syntax",
        "test-bad-wheel",
        "test-cant-build-via-sdist",
        "test-invalid-requirements",
        "test-metadata",
        "test-no-project",
        "test-no-requires",
        "test-optional-hooks",
    ]
    if package == "test-flit":
        pytest.skip(
            reason="Required version of flit was not packaged for Python 3.12 in our channel"
        )
    try:
        pypa_to_conda(
            package_path / package, output_path=tmp_path, distribution="wheel"
        )
    except (
        build.BuildException,
        build.BuildBackendException,
        subprocess.CalledProcessError,
        InvalidRequirement,
    ) as e:
        if package in xfail:
            pytest.xfail(reason=str(e))


def test_ensure_requirements(mocker):
    mock = mocker.patch("conda_pupa.build.main_subshell")
    ensure_requirements(["flit_core"])
    # normalizes/converts the underscore flit_core->flit-core
    assert mock.call_args.args == ("install", "-y", "flit-core")


def test_filter_coverage():
    class tarinfo:
        name = ".git"

    assert filter(tarinfo) is None  # type: ignore


def test_create_build_dir(tmp_path):
    # XXX should "create default output_path" logic live in pypa_to_conda?
    with pytest.raises(build.BuildException):
        pypa_to_conda(tmp_path)
