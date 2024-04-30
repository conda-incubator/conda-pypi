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
$ conda create -n virtualenv python=3.10 pip
$ conda activate virtualenv
$ pip install ...
```

**Editable installs**: conda provides all the dependencies of a package.
`

## Installation

XXX

## Contributing

XXX
