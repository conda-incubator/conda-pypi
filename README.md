# conda-pypi

Better PyPI interoperability for the conda ecosystem.

> [!IMPORTANT]
> This project is still in early stages of development. Don't use it in production (yet).
> We do welcome feedback on what the expected behaviour should have been if something doesn't work!

## What is this?

Includes:

- `conda pip`: A subcommand that converts PyPI packages to `.conda` format for safer installation.
- `conda pupa`: Direct access to conda-pupa functionality for advanced package conversion.
- Adds `EXTERNALLY-MANAGED` to your environments.

**Now powered by conda-pupa** - converts PyPI packages to proper `.conda` packages instead of mixing pip and conda installations.

## Why?

Mixing conda and PyPI is often discouraged in the conda ecosystem.
There are only a handful patterns that are safe to run. This tool
aims to provide a safer way of keeping your conda environments functional
by converting PyPI packages to proper `.conda` packages before installation.

**Key improvements with conda-pupa backend:**
- PyPI packages are converted to `.conda` format before installation
- Better handling of editable installs (`pip install -e`)
- Proper dependency resolution using conda's solver
- No more mixed conda/pip metadata issues

Refer to the [documentation](docs/) for more details.

## Attribution

This project now incorporates [conda-pupa](https://github.com/dholth/conda-pupa) by Daniel Holth, which provides the core PyPI-to-conda conversion functionality.

## Contributing

Please refer to [`CONTRIBUTING.md`](/CONTRIBUTING.md).
