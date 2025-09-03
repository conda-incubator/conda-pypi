# CLI Reference

This reference documents all available commands, options, and usage patterns
for the `conda pypi` command-line interface.

## Overview

`conda-pypi` adds the `conda pypi` subcommand to conda, providing two main
operations:

- `conda pypi install` - Install PyPI packages with conversion to conda
  format
- `conda pypi convert` - Convert PyPI packages to `.conda` format without
  installing

## Global Options

These options are inherited from conda and available for all `conda pypi`
commands:

### Target Environment Specification

```bash
-n ENVIRONMENT, --name ENVIRONMENT
```
Name of the conda environment to operate on. If not specified, uses the
currently active environment.

```bash
-p PATH, --prefix PATH
```
Full path to environment location (i.e. prefix). Use this instead of `-n`
when working with environments outside the default envs directory.

### Output, Prompt, and Flow Control Options

```bash
--json
```
Report all output as JSON. Suitable for using conda programmatically or
parsing output in scripts.

```bash
--console CONSOLE
```
Select the backend to use for normal output rendering. Options depend on
your conda installation.

```bash
-v, --verbose
```
Increase verbosity level. Can be used multiple times:
- Once: detailed output
- Twice: INFO logging
- Thrice: DEBUG logging
- Four times: TRACE logging

```bash
-q, --quiet
```
Do not display progress bar or other non-essential output. Useful for
scripting.

```bash
-d, --dry-run
```
Only display what would have been done without actually performing the
operation. Useful for previewing changes.

```bash
-y, --yes
```
Sets any confirmation values to 'yes' automatically. Users will not be
asked to confirm any operations.

```bash
-h, --help
```
Show help message and exit.

## conda pypi install

Install PyPI packages by converting them to conda format when possible.

### Synopsis

```bash
conda pypi install [options] package [package ...]
conda pypi install [options] -e path
conda pypi install [options] -e vcs+url
```

### Description

The install command takes PyPI packages and converts them to `.conda` format.
Explicitly requested packages are always converted from PyPI, while
dependencies are preferentially installed from conda channels when available.

### Arguments

```bash
package
```
Package specification(s) to install. Can be:
- Package names: `httpx`, `numpy`
- Version specifications: `httpx>=0.28`, `numpy==1.21.*`
- URLs to wheels or source distributions:
  `https://files.pythonhosted.org/packages/...`
- Local file paths: `./my-package-1.0.tar.gz`

### Options

```bash
--override-channels
```
Do not search default or `.condarc` channels during dependency resolution.
Requested packages are always converted from PyPI regardless of this flag,
but dependencies will be forced to convert from PyPI instead of using conda
channels like conda-forge.

```bash
--dry-run
```
Don't actually install anything, just print what would be done. Shows which
packages would be converted from PyPI and which would be installed from conda
channels.

```bash
-e, --editable
```
Install packages in editable mode (development mode). Supports:
- Local directories: `-e ./my-project/`
- VCS URLs: `-e git+https://github.com/user/repo.git`
- VCS URLs with branches: `-e git+https://github.com/user/repo.git@branch`
- VCS URLs with subdirectories:
  `-e git+https://github.com/user/repo.git#subdirectory=sub`

### Examples

Install a single package:
```bash
conda pypi install httpx
```

Install multiple packages:
```bash
conda pypi install httpx numpy pandas
```

Install with version constraints:
```bash
conda pypi install "httpx>=2.25.0" "numpy<1.22"
```

Preview installation without changes:
```bash
conda pypi install --dry-run tensorflow
```

Force dependency resolution from PyPI only:
```bash
conda pypi install --override-channels some-package-with-many-deps
```

Install in editable mode from local directory:
```bash
conda pypi install -e ./my-project/
```

Install in editable mode from git repository:
```bash
conda pypi install -e git+https://github.com/user/project.git
```

Install in specific environment:
```bash
conda pypi install -n myenv httpx
```

Quiet installation for scripting:
```bash
conda pypi install --quiet --yes httpx
```

### Exit Codes

- `0`: Success - all packages installed successfully
- `1`: Failure - one or more packages failed to install

## conda pypi convert

Convert PyPI packages to `.conda` format without installing them.

### Synopsis

```bash
conda pypi convert [options] package [package ...]
```

### Description

The convert command transforms PyPI packages to `.conda` format without
installing them. This is useful for creating conda packages from PyPI
distributions, preparing packages for offline installation, or building
custom conda channels.

### Arguments

```bash
package
```
Package specification(s) to convert. Same format as install command:
- Package names: `httpx`, `numpy`
- Version specifications: `httpx>=2.25.0`, `numpy==1.21.*`
- URLs to wheels: `https://files.pythonhosted.org/packages/...`

### Options

```bash
--override-channels
```
Do not search default or `.condarc` channels during conversion. Since the
convert command only converts the explicitly requested packages (not
dependencies), this flag mainly affects whether conda-pypi checks for
existing conda equivalents before converting.

```bash
-d OUTPUT_DIR, --dest OUTPUT_DIR, -o OUTPUT_DIR, --output-dir OUTPUT_DIR
```
Directory to save converted `.conda` packages. If not specified, saves to
current directory. The directory will be created if it doesn't exist.

### Examples

Convert packages to current directory:
```bash
conda pypi convert httpx packaging
```

Convert to specific directory:
```bash
conda pypi convert -d ./converted-packages httpx numpy
```

Convert without checking for conda equivalents:
```bash
conda pypi convert --override-channels some-package
```

Convert from specific environment:
```bash
conda pypi convert -n myenv -d ./packages httpx
```

Quiet conversion:
```bash
conda pypi convert --quiet -d ./output httpx
```

### Exit Codes

- `0`: Success - all packages converted successfully
- `1`: Failure - one or more packages failed to convert

## Package Specifications

Both install and convert commands accept various package specification
formats:

### Basic Package Names
```bash
conda pypi install httpx
conda pypi install numpy pandas
```

### Version Constraints
```bash
conda pypi install "httpx>=2.25.0"
conda pypi install "numpy>=1.20,<1.22"
conda pypi install "django~=4.0.0"
```

### Exact Versions
```bash
conda pypi install httpx==2.28.1
conda pypi install numpy==1.21.6
```

### URLs
```bash
conda pypi install https://files.pythonhosted.org/packages/.../httpx-2.28.1-py3-none-any.whl
```

### Local Files
```bash
conda pypi install ./dist/mypackage-1.0.tar.gz
conda pypi install /path/to/package.whl
```

### VCS URLs (editable only)
```bash
conda pypi install -e git+https://github.com/user/repo.git
conda pypi install -e git+https://github.com/user/repo.git@branch
conda pypi install -e git+https://github.com/user/repo.git#subdirectory=sub
conda pypi install -e hg+https://bitbucket.org/user/repo
conda pypi install -e svn+https://svn.example.com/repo/trunk
```

## Environment Variables

`conda-pypi` respects standard conda environment variables and adds a few
of its own:

### Conda Variables
- `CONDA_DEFAULT_ENV`: Default environment name
- `CONDA_PREFIX`: Current environment prefix
- `CONDA_CHANNELS`: Default channels (affects dependency resolution)

### Pip Variables
- `PIP_INDEX_URL`: Primary PyPI index URL
- `PIP_EXTRA_INDEX_URL`: Additional PyPI index URLs
- `PIP_TRUSTED_HOST`: Trusted hosts for PyPI access

## Integration with conda list

When `conda-pypi` converts and installs packages, they appear in `conda
list` output and are tracked by conda's package management system. Converted
packages can be removed with `conda remove`.

## Common Usage Patterns

### Development Workflow
```bash
# Set up development environment
conda create -n dev python=3.10 pip
conda activate dev

# Install your project in editable mode
conda pypi install -e .

# Install additional development dependencies
conda pypi install -e git+https://github.com/user/dev-tool.git
```

### Building Custom Packages
```bash
# Convert packages for offline use
conda pypi convert -d ./offline-packages httpx numpy pandas

# Create custom channel
conda index ./offline-packages
```

### Mixed Environment Setup
```bash
# Install scientific stack from conda, other packages from PyPI
conda install numpy scipy matplotlib
conda pypi install some-domain-specific-package
```

## Troubleshooting

### Common Issues

**Package conversion fails**
- Check that the package is available on PyPI
- Try `--override-channels` to skip conda channel checks
- Use `--verbose` to see detailed error messages

**Dependency conflicts**
- Use `--dry-run` to preview what would be installed
- Check if conflicting packages are already installed via conda
- Consider using `--override-channels` for complex dependency trees

**Permission errors**
- Ensure you have write access to the target environment
- Check that the target environment is not marked as protected (check if `conda-meta/frozen` exists).

**Network issues**
- Verify PyPI connectivity
- Check proxy settings if behind corporate firewall
- Use `PIP_TRUSTED_HOST` for internal PyPI mirrors
