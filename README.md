# conda-pypi

Better PyPI interoperability for the conda ecosystem.

> [!IMPORTANT]
> This project is still in early stages of development. Don't use it in production (yet).
> We do welcome feedback on what the expected behaviour should have been if something doesn't work!

## What is this?

Includes:

- `conda pypi install`: Converts PyPI packages to `.conda` format for safer installation.
- `conda pypi convert`: Convert PyPI packages to `.conda` format without installing them.
- `conda pypi convert -d/--dest`: Save converted packages to a specific directory.
- Adds `EXTERNALLY-MANAGED` to your environments to prevent an accidental `pip install`.

## Why?

Mixing conda and PyPI is often discouraged in the conda ecosystem.
There are only a handful patterns that are safe to run. This tool
aims to provide a safer way of keeping your conda environments functional
by converting PyPI packages to proper `.conda` packages before installation.

Refer to the [documentation](docs/) for more details.

## Attribution

This project now incorporates [conda-pupa](https://github.com/dholth/conda-pupa) by Daniel Holth, which provides the core PyPI-to-conda conversion functionality.

## Contributing

Please refer to [`CONTRIBUTING.md`](/CONTRIBUTING.md).
