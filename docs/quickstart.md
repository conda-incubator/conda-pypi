# Quick start

## Installation

`conda-pypi` is a `conda` plugin that needs to be installed next to
`conda` in the `base` environment:

```bash
conda install -n base conda-pypi
```

Once installed, the `conda pip` subcommand becomes available across all your
conda environments.

## Basic usage

`conda-pypi` provides several {doc}`features`. The main functionality is
accessed through the `conda pip` command:

### Installing PyPI packages

Assuming you have an activated conda environment named `my-python-env` that
includes `python` and `pip` installed, and `conda-forge` in your configured
channels, you can use `conda pip install` like this:

```bash
conda pip install requests
```

This will download and convert `requests` from PyPI to `.conda` format
(since it was explicitly requested), but install its dependencies from
conda-forge when available. For example, if `requests` depends on `urllib3`
and `certifi`, and both are available on conda-forge, those dependencies will
be installed from conda rather than PyPI.

```bash
conda pip install build
```

This will download and convert the `build` package from PyPI to `.conda`
format. Even though `python-build` exists on conda-forge, the explicitly
requested package always comes from PyPI to ensure you get exactly what you
asked for. However, its dependencies will preferentially come from conda
channels when available.

```bash
conda pip install some-package-with-many-deps
```

Here's where the hybrid approach really shines:
`some-package-with-many-deps` itself will be converted from PyPI, but
conda-pypi will analyze its dependency tree and:
- Install dependencies like `numpy`, `pandas`, etc. from conda-forge (if
  available)
- Convert only the dependencies that aren't available on conda channels from
  PyPI

```bash
conda pip install --override-channels some-package
```

This forces dependency resolution to use only PyPI, bypassing conda channel
checks for dependencies. The requested package is always converted from PyPI
regardless of this flag.

### Converting packages without installing

You can also convert PyPI packages to `.conda` format without installing
them:

```bash
# Convert to current directory
conda pip convert requests packaging

# Convert to specific directory
conda pip convert -d ./my_packages requests packaging
```

This is useful for creating conda packages from PyPI distributions or
preparing packages for offline installation.

### Development and editable installations

`conda-pypi` supports editable installations for development workflows:

```bash
# Install local project in editable mode
conda pip install -e ./my-project/

# Install from version control in editable mode
conda pip install -e git+https://github.com/user/project.git

# Preview what would be installed
conda pip install --dry-run requests pandas
```


### Lockfiles support

Since `conda-pypi` converts PyPI packages to conda format, they appear as
regular conda packages in `conda list --explicit` lockfiles. This means you
can create reproducible environments using standard conda lockfile workflows:

```bash
# Generate lockfile with all packages (including converted PyPI packages)
conda list --explicit --md5 > environment.lock

# Create environment from lockfile
conda create --name myenv --file environment.lock
```

The generated lockfiles contain standard conda package URLs for all packages,
including those that were originally installed from PyPI:

```
# This file may be used to create an environment using:
# $ conda create --name <env> --file <this file>
# platform: osx-arm64
@EXPLICIT
https://conda.anaconda.org/conda-forge/osx-arm64/python-3.12.2-hdf0ec26_0_cpython.conda#85e91138ae921a2771f57a50120272bd
https://conda.anaconda.org/conda-forge/noarch/pip-24.0-pyhd8ed1ab_0.conda#f586ac1e56c8638b64f9c8122a7b8a67
file:///path/to/conda/envs/myenv/conda-bld/converted-requests-2.32.2-py312_0.conda#abcd1234
```

This unified approach eliminates the complexity of managing separate PyPI and
conda package lists, providing a single source of truth for environment
reproduction.

### Environment protection

`conda-pypi` ships a special file called `EXTERNALLY-MANAGED` that helps
protect your conda environments from accidental pip usage that could break
their integrity. This file is automatically installed in the `base`
environment, all new environments that include `pip`, and existing
environments that already have `pip` after running a conda command on them.

More details about this protection mechanism can be found at
{ref}`externally-managed`.
