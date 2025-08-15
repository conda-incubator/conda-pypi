"""
Generate repodata.json converted from wheel metadata.
"""

import hashlib
import os

import packaging.tags
import packaging.utils
import ruamel.yaml
import typer
from packaging.utils import canonicalize_name
from pydantic import BaseModel
from pypi_simple import ProjectPage, PyPISimple

from conda_pypi.translate import FileDistribution, requires_to_conda

app = typer.Typer()

yaml = ruamel.yaml.YAML(typ="safe", pure=True)


class Package(BaseModel):
    build: str = ""
    build_number: int = 0
    depends: list[str] = []
    extras: dict[str, list[str]] = {}
    md5: str | None = None
    name: str = ""
    sha256: str | None = None
    size: int = 0
    subdir: str = ""
    timestamp: int = 0
    version: str = ""


class RepoData(BaseModel):
    info: dict
    packages: dict[str, Package]
    # "packages.conda": list[str]
    # remove: list[Package]
    repodata_version: int


def compatible_wheel(filename):
    """
    Compare filename with supported tags, determine if wheel is compatible.

    An installer would rank the wheels based on the order of sys_tags().
    """
    # TODO get sys_tags from target Python interpreter, not interpreter running synth.py
    name, version, build_tag, tags = packaging.utils.parse_wheel_filename(filename)
    supported_tags = list(packaging.tags.sys_tags())
    return not tags.isdisjoint(supported_tags)


def extract_version_of_project(
    project_page: ProjectPage, version: str, download: bool, download_dir: str
):
    """
    Extract the version and details of the project from the project page.
    """
    for package in project_page.packages:
        if package.version == version and package.filename.endswith(".whl"):
            # hack to select the compatible wheels (macOS, arm64, Python 3.12)
            if not compatible_wheel(package.filename):
                continue
            package_metadata = pypi_simple().get_package_metadata(package)
            package_data = FileDistribution(package_metadata)

            requirements, extras = requires_to_conda(package_data.requires)

            python_version = package_data.metadata["requires-python"]
            requires_python = "python"
            if python_version:
                requires_python = f"python { python_version }"
            depends = [requires_python] + requirements

            # provenance = pypi.get_provenance(package)
            pkg_sha256 = package.digests.get("sha256")
            build = package.filename.split("-", 2)[-1].removesuffix(".whl")
            size = 0
            md5 = ""
            if download:
                pkg_path = os.path.join(download_dir, package.filename)
                pypi_simple().download_package(package, path=pkg_path)
                size = os.path.getsize(pkg_path)
                with open(pkg_path, "rb") as f:
                    md5 = hashlib.md5(f.read()).hexdigest()

            return (
                package.filename,
                Package(
                    name=canonicalize_name(package.project),
                    version=package.version,
                    # sha256=pkg_sha256,
                    size=size,
                    # md5=md5,
                    depends=depends,
                    build=build,
                    subdir="noarch",
                    extras=extras,
                ),
                package.url,
            )
    return "0.0.0", Package(), "https://www.example.com/does_not_exist.whl"


@app.command()
def create_api(
    config_file: str = typer.Option("config.yaml", help="filename of config file"),
    repo_dir: str = typer.Option(
        "synthetic_repo", help="Directory where a conda repo will be created"
    ),
    populate: bool = typer.Option(False, help="Populate the repo with wheels"),
):
    """
    Create a repodata.json file based on the list of projects provided.
    """

    with open(config_file, "rb") as fh:
        requested_packages = yaml.load(fh)

    noarch_dir = os.path.join(repo_dir, "noarch")
    os.makedirs(noarch_dir, exist_ok=True)

    conda_style_packages = {}
    # Make an API request to PyPI
    try:
        for package_name, versions in requested_packages.items():
            project_page = pypi_simple().get_project_page(package_name)
            for version in versions:
                full_name, package, whl_url = extract_version_of_project(
                    project_page, version, populate, noarch_dir
                )
                # print(package)
                conda_style_packages.update({full_name: package})

    except Exception as e:
        typer.echo(f"Error fetching package info: {e}")
        raise e

    # Create API definition
    repodata = RepoData(
        info={"subdir": "noarch"},  # default for now
        packages=conda_style_packages,
        # "packages.conda": [package_name],
        # "pypi_info": package_info,
        repodata_version=1,
    )

    # Save to output file
    noarch_dir = os.path.join(repo_dir, "noarch")
    os.makedirs(noarch_dir, exist_ok=True)
    repodata_file = os.path.join(noarch_dir, "repodata.json")
    with open(repodata_file, "w") as f:
        f.write(repodata.model_dump_json(indent=2, exclude_none=True))
    typer.echo(f"Repodata saved to {repodata_file}")


def pypi_simple():
    global pypi
    try:
        return pypi
    except NameError:
        pypi = PyPISimple()
    return pypi


if __name__ == "__main__":  # pragma: no cover
    app()
