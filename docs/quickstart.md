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

`conda-pypi` integrates with `conda list --explicit` to add PyPI package
information to your `@EXPLICIT` lockfiles. It also integrates with `conda
install` and `conda create` to automatically process these PyPI lines when
recreating environments from lockfiles. See more at {ref}`pypi-lines`.

You can generate lockfiles with PyPI packages included using `conda list
--explicit --md5 > environment.lock`, or generate lockfiles without PyPI
packages using `conda list --explicit --no-pip > environment.lock`.

The generated lockfiles include PyPI packages as comment lines with a
simplified format:

```
# This file may be used to create an environment using:
# $ conda create --name <env> --file <this file>
# platform: osx-arm64
@EXPLICIT
https://conda.anaconda.org/conda-forge/osx-arm64/python-3.12.2-hdf0ec26_0_cpython.conda#85e91138ae921a2771f57a50120272bd
https://conda.anaconda.org/conda-forge/noarch/pip-24.0-pyhd8ed1ab_0.conda#f586ac1e56c8638b64f9c8122a7b8a67
# The following lines were added by conda-pypi v0.1.0
# This is an experimental feature subject to change. Do not use in
# production.
# pypi: requests==2.32.2 --python-version 3.12
# pypi: packaging==24.0 --python-version 3.12
# pypi: some-converted-package==1.0.0 --python-version 3.12 --record-checksum=md5:placeholder
```

When you create or install from a lockfile containing PyPI lines,
conda-pypi automatically processes them. You can create an environment from a
lockfile using `conda create --name myenv --file environment.lock`, and PyPI
packages will be automatically installed. Similarly, you can install packages
from a lockfile into an existing environment using `conda install --file
environment.lock`.

The PyPI packages in the lockfile are processed using the same hybrid
approach as `conda pip install`, installing from conda channels when
available and otherwise converting from PyPI format.

### Environment protection

`conda-pypi` ships a special file called `EXTERNALLY-MANAGED` that helps
protect your conda environments from accidental pip usage that could break
their integrity. This file is automatically installed in the `base`
environment, all new environments that include `pip`, and existing
environments that already have `pip` after running a conda command on them.

More details about this protection mechanism can be found at
{ref}`externally-managed`.
