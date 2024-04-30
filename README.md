# conda-pypi

Better PyPI interoperability for the conda ecosystem.

## What is this?

Includes:

- `conda pip`: A subcommand that wraps `pip` to make it work with `conda` in a better way.
- Adds `EXTERNALLY-MANAGED` to your environments.

## Why?

Mixing conda and PyPI is often discouraged in the conda ecosystem.
There are only a handful patterns that are safe:

**Only Python & pip environments**: `conda` only provides `python` and `pip`.
All other packages are _always_ installed with `pip`:

```bash
$ conda create -n pip-environment python=3.10 pip
$ conda activate pip-environment
$ pip install ...
```

**Editable installs**: conda provides all the dependencies of a given package.
Then that package is installed on top in editable mode, without addressing dependencies
to make sure we don't accidentally override conda files:

```bash
$ git clone git@github.com:owner/package.git
$ conda create -n editable-install package --deps-only
$ conda activate editable-install
$ pip install -e . --no-deps
```

Why do we say these are one of the few safe usages of conda & pip? Because of the following pitfalls:

- xxx
- xxx
- xxx

## Installation

XXX

## Contributing

Please refer to [`CONTRIBUTING.md`](/CONTRIBUTING.md).
