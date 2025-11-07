import pytest

from pytest import MonkeyPatch

from conda.testing.fixtures import CondaCLIFixture
from conda.models.match_spec import MatchSpec

from conda_pypi.convert_tree import ConvertTree


@pytest.mark.parametrize(
    "packages", 
    [
        pytest.param(("imagesize",), id="imagesize"),  # small package, few dependencies
        pytest.param(("scipy",), id="scipy"),  # larger package 
        pytest.param(("jupyterlab",), id="jupyterlab")
    ]
)
def test_conda_pypi_install_basic(
    tmp_path_factory,
    conda_cli: CondaCLIFixture,
    packages: tuple[str],
    benchmark,
    monkeypatch: MonkeyPatch,
):
    """Benchmark basic conda pypi install functionality."""
    def setup():
        # Setup function is run every time. So, using benchmarks to run multiple
        # iterations of the test will create new paths for repo_dir and
        # prefix for each iteration. This ensures a clean test without any
        # cached packages and in a clean environment.
        repo_dir = tmp_path_factory.mktemp(f"{'-'.join(packages)}-pkg-repo")
        prefix = str(tmp_path_factory.mktemp(f"{'-'.join(packages)}"))

        monkeypatch.setattr("platformdirs.user_data_dir", lambda s: str(repo_dir))

        conda_cli("create", "--yes", "--prefix", prefix, "python=3.11")
        return (prefix,), {}

    def target(prefix):
        _, _, rc = conda_cli(
            "pypi",
            "--yes",
            "install",
            "--prefix",
            prefix,
            *packages,
        )
        return rc
    
    result = benchmark.pedantic(
        target,
        setup=setup,
        rounds=2,
        warmup_rounds=0  # no warm up, cleaning the cache every time
    )
    assert result == 0


@pytest.mark.benchmark
@pytest.mark.parametrize(
    "packages", 
    [
        pytest.param(("imagesize",), id="imagesize"),    # small package, few dependencies
        pytest.param(("jupyterlab",), id="jupyterlab"),  # large package
        pytest.param(("numpy>2.0",), id="numpy>2.0"),    # package with version constraint
    ]
)
def test_convert_tree(
    tmp_path_factory,
    conda_cli: CondaCLIFixture,
    packages: tuple[str],
    benchmark,
):
    """Benchmark convert_tree. This test overrides channels so the whole
    dependency tree is converted.
    """
    def setup():
        repo_dir = tmp_path_factory.mktemp(f"{'-'.join(packages)}-pkg-repo")
        prefix = str(tmp_path_factory.mktemp(f"{'-'.join(packages)}"))
        conda_cli("create", "--yes", "--prefix", prefix, "python=3.11")

        tree_converter =  ConvertTree(
            prefix=prefix,
            override_channels=True,
            repo=repo_dir
        )
        return (tree_converter,), {}

    def target(tree_converter):
        match_specs = [MatchSpec(pkg) for pkg in packages]
        tree_converter.convert_tree(match_specs)
    
    benchmark.pedantic(
        target,
        setup=setup,
        rounds=2,
        warmup_rounds=0  # no warm up, cleaning the cache every time
    )
