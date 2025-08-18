import json
import subprocess
from pathlib import Path

import pytest
from conda.base.context import context
from conda.cli.main import main_subshell
from conda.core.prefix_data import PrefixData
from packaging.requirements import InvalidRequirement

import build
import conda_pupa.dependencies_subprocess
from conda_pupa.build import filter, pypa_to_conda
from conda_pupa.dependencies import ensure_requirements


def test_editable(tmp_path):
    # Other tests can change context.target_prefix by calling "conda install
    # --prefix", so we use default_prefix; could alternatively reset context.
    pypa_to_conda(
        Path(__file__).parents[1],
        output_path=tmp_path,
        distribution="editable",
        prefix=Path(context.default_prefix),
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
            package_path / package,
            output_path=tmp_path,
            distribution="wheel",
            prefix=Path(context.default_prefix),
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
    mock = mocker.patch("conda_pupa.dependencies.main_subshell")
    ensure_requirements(["flit_core"], prefix=Path())
    # normalizes/converts the underscore flit_core->flit-core
    assert mock.call_args.args == ("install", "--prefix", ".", "-y", "flit-core")


def test_filter_coverage():
    class tarinfo:
        name = ".git"

    assert filter(tarinfo) is None  # type: ignore


def test_create_build_dir(tmp_path):
    # XXX should "create default output_path" logic live in pypa_to_conda?
    with pytest.raises(build.BuildException):
        pypa_to_conda(tmp_path, prefix=Path(context.default_prefix))


## Test pupa installed in different environment than editable package / activated environment...


def test_build_in_env(tmp_path):
    main_subshell(
        "create",
        "--prefix",
        str(tmp_path / "env"),
        "-y",
        "python",
        "python-build",
    )

    prefix = str(tmp_path / "env")

    # error, or click doesn't integrate that well with conda's plugins?
    with pytest.raises(SystemExit):
        main_subshell(
            "pupa",
            "--prefix",
            prefix,
            "--output-folder",
            str(tmp_path),
            "-e",
            str(Path(__file__).parent / "packages" / "has-build-dep"),
        )

    installed = [
        record.name for record in PrefixData(prefix, pip_interop_enabled=True).iter_records()
    ]

    assert "sphinxcontrib" in installed


def test_dependencies_subprocess():
    """
    Normally called in a way that doesn't measure coverage.
    """
    dependencies = ["xyzzy", "conda"]
    missing_dependencies = conda_pupa.dependencies_subprocess.main(
        ["-", "-r", json.dumps(dependencies)]
    )
    # A list per checked dependency, if that dependency or its dependencies are
    # missing.
    assert json.loads(missing_dependencies) == [["xyzzy"]]
