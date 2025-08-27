# Quick start

## Installation

`conda-pypi` is a `conda` plugin that needs to be installed next to
`conda` in the `base` environment:

```bash
conda install -n base conda-pypi
```

Once installed, the `conda pypi` subcommand becomes available across all your
conda environments.

## Basic usage

`conda-pypi` provides several {doc}`features`. The main functionality is
accessed through the `conda pypi` command:

### Installing PyPI packages

Assuming you have an activated conda environment named `my-python-env` that
includes `python` and `pip` installed, and a configured conda channel, you can
use `conda pypi install` like this:

```bash
conda pypi install niquests
```

This will download and convert `niquests` from PyPI to `.conda` format
(since it was explicitly requested), but install its dependencies from
the conda channel when available. For example, if `niquests` depends on
`urllib3` and `certifi`, and both are available on the conda channel, those
dependencies will be installed from conda rather than PyPI.

```bash
conda pypi install build
```

This will download and convert the `build` package from PyPI to `.conda`
format. Even though `python-build` exists on conda, the explicitly requested
package always comes from PyPI to ensure you get exactly what you asked for.
However, its dependencies will preferentially come from conda channels when
available.

```bash
conda pypi install some-package-with-many-deps
```

Here's where the hybrid approach really shines:
`some-package-with-many-deps` itself will be converted from PyPI, but
conda-pypi will analyze its dependency tree and:
- Install dependencies like `numpy`, `pandas`, etc. from the conda channel (if
  available)
- Convert only the dependencies that aren't available on conda channels from
  PyPI

```bash
conda pypi install --override-channels some-package
```

This forces dependency resolution to use only PyPI, bypassing conda channel
checks for dependencies. The requested package is always converted from PyPI
regardless of this flag.

### Converting packages without installing

You can also convert PyPI packages to `.conda` format without installing
them:

```bash
# Convert to current directory
conda pypi convert niquests rope

# Convert to specific directory
conda pypi convert -d ./my_packages niquests rope
```

This is useful for creating conda packages from PyPI distributions or
preparing packages for offline installation.

### Development and editable installations

`conda-pypi` supports editable installations for development workflows:

```bash
# Install local project in editable mode
conda pypi install -e ./my-project/

# Install from version control in editable mode
conda pypi install -e git+https://github.com/user/project.git

# Preview what would be installed
conda pypi install --dry-run niquests pandas
```

### Lockfiles support

`conda-pypi` integrates with `conda list --explicit` to add some custom comments so your `@EXPLICIT` lockfiles contain PyPI information. `conda-pypi` also integrates with `conda install` and `conda create` to process these special lines. See more at {ref}`pypi-lines`.

You can generate these lockfiles with `conda list --explicit --md5`, and they will look like this:

```
# This file may be used to create an environment using:
# $ conda create --name <env> --file <this file>
# platform: osx-arm64
@EXPLICIT
https://conda.anaconda.org/conda-forge/osx-arm64/bzip2-1.0.8-h93a5062_5.conda#1bbc659ca658bfd49a481b5ef7a0f40f
https://conda.anaconda.org/conda-forge/osx-arm64/ca-certificates-2024.2.2-hf0a4a13_0.conda#fb416a1795f18dcc5a038bc2dc54edf9
https://conda.anaconda.org/conda-forge/osx-arm64/libexpat-2.6.2-hebf3989_0.conda#e3cde7cfa87f82f7cb13d482d5e0ad09
https://conda.anaconda.org/conda-forge/osx-arm64/libffi-3.4.2-h3422bc3_5.tar.bz2#086914b672be056eb70fd4285b6783b6
https://conda.anaconda.org/conda-forge/osx-arm64/libzlib-1.2.13-h53f4e23_5.conda#1a47f5236db2e06a320ffa0392f81bd8
https://conda.anaconda.org/conda-forge/osx-arm64/ncurses-6.4.20240210-h078ce10_0.conda#616ae8691e6608527d0071e6766dcb81
https://conda.anaconda.org/conda-forge/noarch/tzdata-2024a-h0c530f3_0.conda#161081fc7cec0bfda0d86d7cb595f8d8
https://conda.anaconda.org/conda-forge/osx-arm64/xz-5.2.6-h57fd34a_0.tar.bz2#39c6b54e94014701dd157f4f576ed211
https://conda.anaconda.org/conda-forge/osx-arm64/libsqlite-3.45.2-h091b4b1_0.conda#9d07427ee5bd9afd1e11ce14368a48d6
https://conda.anaconda.org/conda-forge/osx-arm64/openssl-3.2.1-h0d3ecfb_1.conda#eb580fb888d93d5d550c557323ac5cee
https://conda.anaconda.org/conda-forge/osx-arm64/readline-8.2-h92ec313_1.conda#8cbb776a2f641b943d413b3e19df71f4
https://conda.anaconda.org/conda-forge/osx-arm64/tk-8.6.13-h5083fa2_1.conda#b50a57ba89c32b62428b71a875291c9b
https://conda.anaconda.org/conda-forge/osx-arm64/python-3.12.2-hdf0ec26_0_cpython.conda#85e91138ae921a2771f57a50120272bd
https://conda.anaconda.org/conda-forge/noarch/absl-py-2.1.0-pyhd8ed1ab_0.conda#035d1d58677c13ec93122d9eb6b8803b
https://conda.anaconda.org/conda-forge/noarch/setuptools-69.2.0-pyhd8ed1ab_0.conda#da214ecd521a720a9d521c68047682dc
https://conda.anaconda.org/conda-forge/noarch/wheel-0.43.0-pyhd8ed1ab_1.conda#0b5293a157c2b5cd513dd1b03d8d3aae
https://conda.anaconda.org/conda-forge/noarch/pip-24.0-pyhd8ed1ab_0.conda#f586ac1e56c8638b64f9c8122a7b8a67
# The following lines were added by conda-pypi v0.1.0
# This is an experimental feature subject to change. Do not use in production.
# pypi: charset-normalizer==3.3.2 --python-version 3.12.2 --implementation cp --abi cp312 --platform macosx_11_0_arm64 --record-checksum=md5:a88a07f3a23748b3d78b24ca3812e7d8
# pypi: certifi==2024.2.2 --python-version 3.12.2 --implementation cp --record-checksum=md5:1c186605aa7d0c050cf4ef147fcf750d
# pypi: tf-slim==1.1.0 --python-version 3.12.2 --implementation cp --record-checksum=md5:96c65c0d90cd8c93f3bbe22ee34190c5
# pypi: aaargh==0.7.1 --python-version 3.12.2 --implementation cp --record-checksum=md5:55f5aa1765064955792866812afdef6f
# pypi: requests==2.32.2 --python-version 3.12.2 --implementation cp --record-checksum=md5:d7e8849718b3ffb565fd3cbe2575ea97
# pypi: 5-exercise-upload-to-pypi==1.2 --python-version 3.12.2 --implementation cp --record-checksum=md5:c96a1cd6037f6e3b659e2139b0839c97
# pypi: idna==3.7 --python-version 3.12.2 --implementation cp --record-checksum=md5:5b2f9f2c52705a9b1e32818f1b387356
# pypi: urllib3==2.2.1 --python-version 3.12.2 --implementation cp --record-checksum=md5:1bd9312a95c73a644f721ca96c9d8b45
```

### Environment protection

`conda-pypi` ships a special file called `EXTERNALLY-MANAGED` that helps
protect your conda environments from accidental pip usage that could break
their integrity. This file is automatically installed in the `base`
environment, all new environments, and existing environments that after running
a `conda pypi` command on them.

More details about this protection mechanism can be found at
{ref}`externally-managed`.
