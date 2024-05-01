# Quick start

## Installation

`conda-pypi` is a `conda` plugin that needs to be installed next to `conda` in the `base` environment:

```
conda install -n base conda-pypi
```

## Basic usage

`conda-pypi` provides several functionalities:

- A `conda pip` subcommand
- A `post_command` hook that will place environment proctection markers

Their usage is discussed below.

### New environments

You need to create a new environment with `python` _and_ `pip`, because we will rely on the target `pip` to process the potential PyPI dependencies:

```
conda create -n my-python-env python pip
```

### Existing environments

Assuming you have an activated conda environment named `my-python-env` that includes `python` and `pip` installed:

```
conda pip install requests
```

This will install `requests` from conda, along with all its dependencies, because everything is available. The dependency tree translates one-to-one from PyPI to conda, so there are no issues.

```
conda pip install build
```

This will install the `python-build` package from conda-forge. Note how `conda pip` knows how to map the different project names. This is done via semi-automated mappings provided by the `grayskull` and `cf-graph-countyfair` projects.

```
conda pip install PyQt5
```

This will install `pyqt=5` from conda, which also brings `qt=5` separately. This is because `pyqt` on conda _depennds_ on the Qt libraries instead of bundling them in the same package. Again, the `PyQt5 -> pyqt` mapping is handled as expected.

```
conda pip install ib_insync
```

This will install `ib-insync` from conda-forge. Since the conda ecosystem does not normalize dashes and underscores, we have to try all the combinations when searching for the equivalent in conda-forge. This heuristic is not as robust as the mappings mentioned above, though! We are hoping
there are no conda packages where the underscore and dash variants refer to different packages.

```
conda pip install 5-exercise-upload-to-pypi
```

This package is not available on conda-forge. We will analyze the dependency tree and install all the available ones with `conda`. The rest will be installed with `pip install --no-deps`.


### Environment protection

`conda-pypi` ships a special file, `EXTERNALLY-MANAGED`, that will be installed in:

- The `base` environment.
- All new environments that include `pip`.
- Existing environments that `pip`, but only after running a conda command on them.

This file is designed after [PEP668](https://peps.python.org/pep-0668/). You can read more about in [Externally Managed Environments at packaging.python.org](https://packaging.python.org/en/latest/specifications/externally-managed-environments/).

Essentially, the presence of this file in a given environment will prevent users from using `pip` directly on them. An [informative error message](https://github.com/jaimergp/conda-pip/blob/main/conda_pypi/data/EXTERNALLY-MANAGED) is provided instead.