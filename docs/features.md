# Features

`conda-pypi` uses the `conda` plugin system to implement several features that make `conda` integrate better with the PyPI ecosystem:

## The `conda pip` subcommand

This subcommand provides a safer way to install PyPI packages in conda environments by converting them to conda format when possible. It offers two main subcommands that handle different aspects of PyPI integration.

### `conda pip install`

The install command takes PyPI packages and converts them to `.conda` format when possible, falling back to direct pip installation when needed. The process begins with dependency resolution using pip's own dependency resolver to determine what packages need to be installed.

Explicitly requested packages are always installed from PyPI and converted to `.conda` format to ensure you get exactly what you asked for. For dependencies, conda-pypi intelligently chooses the best source using a conda-first approach. If a dependency is available on conda channels, it will be installed with `conda` directly. If not available on conda channels, the dependency will be converted from PyPI to `.conda` format.

The system uses multiple sources for package name mapping, including automated mappings from the grayskull project, name normalization that handles dash and underscore variants, and direct searches of configured conda channels for equivalent packages. VCS and editable packages are handled as special cases and installed directly with `pip --no-deps`.

You can preview what would be installed without making changes using `--dry-run`, install packages in editable development mode with `--editable` or `-e`, and force dependency resolution from PyPI without using conda channels using `--override-channels`.

### `conda pip convert`

The convert command transforms PyPI packages to `.conda` format without installing them, which is useful for creating conda packages from PyPI distributions or preparing packages for offline installation. You can specify where to save the converted packages using `-d`, `--dest`, or `--output-dir`. The command supports converting multiple packages at once and can skip conda channel checks entirely with `--override-channels` to convert directly from PyPI.

Here are some common usage patterns:

```bash
# Convert packages to current directory
conda pip convert requests packaging

# Convert to specific directory
conda pip convert -d ./my_packages requests packaging

# Convert without checking conda channels first
conda pip convert --override-channels some-pypi-only-package
```

## PyPI-to-Conda Conversion Engine

`conda-pypi` includes a powerful conversion engine that enables direct conversion of Python wheels to `.conda` packages with proper translation of Python package metadata to conda format. The system includes intelligent mapping of PyPI dependencies to conda equivalents and provides cross-platform support for package conversion, ensuring that converted packages work seamlessly across different operating systems and architectures.

(pypi-lines)=

## `conda list` integrations

While `conda` has native support for listing PyPI dependencies as part of `conda list`, this is not enabled in all output modes. Notably, `conda list --explicit`, which is sometimes used as a lockfile replacement, does not include any information about PyPI dependencies.

To address this limitation, we have added a post-command plugin that lists PyPI dependencies via `# pypi:` comments. This is currently an experimental, non-standard extension of the file format that is subject to change. The simplified syntax focuses on essential package information including the package name, version, and Python version, with optional placeholder checksums when the `--md5` flag is used.

The current implementation automatically detects only packages installed via conda-pypi conversion and excludes PyPI packages from explicit listings when you use the `--no-pip` option. The format looks like this:

```
# pypi: <name>==<version> --python-version <version> [--record-checksum=md5:placeholder]
```

Here are some example PyPI lines you might see:
```
# pypi: requests==2.32.2 --python-version 3.12
# pypi: packaging==24.0 --python-version 3.12
# pypi: converted-package==1.0.0 --python-version 3.12 --record-checksum=md5:placeholder
```

## `conda install` integrations

A post-command plugin automatically processes `@EXPLICIT` lockfiles and searches for `# pypi:` lines during `conda install` and `conda create` operations. When PyPI lines are found, the packages are automatically installed using conda-pypi's hybrid approach, working transparently with existing conda workflows.

The system provides clear error messages if PyPI package installation fails and uses the same smart conversion logic as `conda pip install` for dependency resolution. This enables full environment reproducibility that includes both conda and converted PyPI packages, ensuring that environments can be recreated exactly as they were originally configured.

## Editable Package Support

`conda-pypi` provides comprehensive support for editable (development) installations, making it ideal for development environments where code is frequently modified. The system supports both version control system packages and local packages.

For VCS packages, you can install directly from git URLs with automatic cloning. The system caches VCS repositories locally for improved performance and manages temporary directories and repository clones automatically. Local package support allows you to install packages from local project directories in editable mode, which is perfect for active development workflows.

Here are some common usage patterns for editable installations:

```bash
# Install from git repository in editable mode
conda pip install -e git+https://github.com/user/project.git

# Install local project in editable mode
conda pip install -e ./my-project/

# Multiple editable packages
conda pip install -e ./package1/ -e git+https://github.com/user/package2.git
```

## `conda env` integrations

:::{admonition} Coming soon
:class: seealso

`environment.yml` files famously allow a `pip` subsection in their `dependencies`. This is handled internally by `conda env` via a `pip` subprocess. We are adding new plugin hooks so `conda-pypi` can handle these in the same way we do with the `conda pip` subcommand.
:::

(externally-managed)=

## Environment marker files

`conda-pypi` adds support for [PEP-668](https://peps.python.org/pep-0668/)'s [`EXTERNALLY-MANAGED`](https://packaging.python.org/en/latest/specifications/externally-managed-environments/) environment marker files. These files tell `pip` and other PyPI installers not to install or remove any packages in that environment, guiding users towards safer alternatives.

When these marker files are present, they display a message letting users know that the `conda pip` subcommand is available as a safer alternative. The primary goal is to avoid accidental overwrites that could break your conda environment. If you need to use `pip` directly, you can still do so by adding the `--break-system-packages` flag, though this is generally not recommended in conda environments.
