# conda-pypi

Better PyPI interoperability for the conda ecosystem.

> [!IMPORTANT]
> This project is still in early stages of development. Don't use it in production (yet).
> We do welcome feedback on what the expected behaviour should have been if something doesn't work!

## What is this?

Includes:

- `conda pip`: A subcommand that wraps `pip` to make it work with `conda` in a better way.
- Adds `EXTERNALLY-MANAGED` to your environments.

## Why?

Mixing conda and PyPI is often discouraged in the conda ecosystem.
There are only a handful patterns that are safe to run. This tool
aims to provide a safer way of keeping your conda environments functional
while mixing it with PyPI dependencies. Refer to the [documentation](docs/)
for more details.

## Contributing

Please refer to [`CONTRIBUTING.md`](/CONTRIBUTING.md).
