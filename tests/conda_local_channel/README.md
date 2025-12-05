# Mock Conda Channel for Tests

This directory contains a mock conda channel used by the test suite to verify dependency resolution and package installation without requiring network access or actual conversion.

## Structure

- `noarch/` - Platform-independent packages subdirectory (standard conda channel structure)
  - `repodata.json` - Package metadata (moved from project root)
  - `*.whl` - Wheel files referenced in repodata.json (14 packages)
- `osx-arm64/` - macOS Apple Silicon packages
  - `repodata.json` - Package metadata for this platform
  - `*.conda` - Conda packages (Python 3.12 + dependencies, ~16 packages)
- `linux-64/` - Linux x86_64 packages
  - `repodata.json` - Package metadata for this platform
  - `*.conda` - Conda packages (Python 3.12 + dependencies, ~16 packages)
- `provision_wheels.py` - Script to download wheel files from PyPI
- `provision_conda_packages.py` - Script to download conda packages (Python + deps) from conda-forge
- `generate_index.py` - Script to generate compressed indexes for all subdirectories
- `README.md` - This file

## Setup

Before running tests that use the `conda_local_channel` fixture, you need to provision the wheel files.
This only needs to be done if you update the `repodata.json` file for any reason becuase all of the wheel
files are currently committed to the repository itself.

### Download Wheel Files

Run the provisioning script to download all referenced wheels from PyPI:

```bash
cd tests/conda_local_channel
python provision_wheels.py
```

This will:
- Read `noarch/repodata.json` to find required wheels
- Download each wheel from PyPI (if not already present)
- Verify SHA256 checksums match the metadata
- Report any download failures

The script is idempotent - if wheels already exist with correct checksums, they won't be re-downloaded.

### Download Conda Packages (Python + Dependencies)

To provision Python 3.12 and all its dependencies for both osx-arm64 and linux-64:

```bash
cd tests/conda_local_channel
python provision_conda_packages.py
```

This will:
- Resolve Python 3.12 dependencies using micromamba
- Download ~16 packages per platform (~46MB total)
- Verify checksums for all packages
- Create basic repodata.json for each platform

**Note:** This step is required for integration tests that need Python without external channels.

### Platform Support

The channel includes packages for:
- `noarch` - Pure Python wheels (platform-independent)
- `osx-arm64` - macOS Apple Silicon
- `linux-64` - Linux x86_64

To add additional platforms, edit `PLATFORMS` list in `provision_conda_packages.py`.

### Complete Setup Process

For a fully functional local conda channel:

```bash
cd tests/conda_local_channel

# 1. Download conda packages (Python + deps)
python provision_conda_packages.py

# 2. Download Python wheels
python provision_wheels.py

# 3. (Optional) Generate compressed indexes
python generate_index.py
```

After these steps, the channel contains:
- Python 3.12 + 15 dependencies (osx-arm64 and linux-64)
- 14 Python wheels (noarch)
- Total: ~50MB

### Generate Compressed Indexes (Optional)

To generate compressed index files for more realistic testing, run:

```bash
cd tests/conda_local_channel
python generate_index.py
```

This creates compressed indexes (`.zst` files) for all subdirectories using conda-index. The fixture works fine without this step, but compressed indexes are more realistic.

## Usage in Tests

The `conda_local_channel` pytest fixture starts an HTTP server serving this directory on port 8037.

### Basic Usage

```python
def test_with_conda_channel(conda_local_channel):
    """
    conda_local_channel is "http://localhost:8037"
    """
    # Use the channel URL in your test
    assert conda_local_channel == "http://localhost:8037"
```

### Accessing Channel Metadata

```python
def test_channel_metadata(conda_local_channel):
    import urllib.request
    import json

    url = f"{conda_local_channel}/noarch/repodata.json"
    with urllib.request.urlopen(url) as response:
        repodata = json.loads(response.read())

    # Verify packages are available
    assert "packages.whl" in repodata
    assert "requests-2.32.5-py3-none-any.whl" in repodata["packages.whl"]
```

### Integration with ConvertTree

```python
from conda.models.channel import Channel
from conda_pypi.convert_tree import ConvertTree


def test_install_from_channel(tmp_env, conda_local_channel):
    with tmp_env("python=3.12") as prefix:
        # Create channel from fixture URL
        channel = Channel(conda_local_channel)

        # Use in dependency resolution
        converter = ConvertTree(prefix, repo=REPO)
        # Configure solver to use local channel...
```

## Available Packages

The channel contains 14 pre-converted packages (as of setup):

- `requests-2.32.5`
- `fastapi-0.116.1`
- `pydantic-2.11.7`
- `pydantic_core-2.33.2`
- `starlette-0.47.2`
- `anyio-4.9.0`
- `sniffio-1.3.1`
- `idna-3.10`
- `typing_extensions-4.14.1`
- `typing_inspection-0.4.1`
- `annotated_types-0.7.0`
- `setuptools-78.1.1`
- `wheel-0.45.1`
- `abqpy-2023.7.10`

All packages are in the `noarch` subdirectory (platform-independent).

## Fixture Details

**Fixture name:** `conda_local_channel`

**Scope:** `session` (starts once per test session)

**Port:** 8036 (separate from PyPI server on 8035)

**Server:** Python's built-in `http.server` module

**Process management:** `pytest-xprocess` (automatic startup/cleanup)

## Maintenance

### Adding New Packages

To add new packages to the channel:

1. Download the wheel file to `noarch/`
2. Update `noarch/repodata.json` with package metadata:
   - name, version, build, build_number
   - depends (list of dependencies)
   - sha256, size, timestamp
   - noarch: "python"
3. Run `python provision_wheels.py` to verify checksums
4. Update `repodata.json.zst` by running `zstd repodata.json`.

### Updating Existing Packages

1. Remove old wheel file from `noarch/`
2. Update metadata in `noarch/repodata.json`
3. Run `python provision_wheels.py` to download new version
4. Update `repodata.json.zst` by running `zstd repodata.json`.

## Troubleshooting

### Download Failures

If `provision_wheels.py` fails to download a wheel:

1. Check the error message - it may be a network issue
2. Manually download the wheel from PyPI:
   - Visit `https://pypi.org/project/{package_name}/#files`
   - Download the wheel file matching the filename in `repodata.json`
3. Place the wheel in `noarch/`
4. Re-run `provision_wheels.py` to verify checksum

### Port Conflicts

If port 8036 is already in use:

1. Change the port in `tests/conftest.py` (line ~56)
2. Update test expectations if they hardcode the port number

### Checksum Mismatches

If checksums don't match:

1. Verify the wheel file isn't corrupted
2. Re-download from PyPI
3. Update `repodata.json` if the upstream package was updated
