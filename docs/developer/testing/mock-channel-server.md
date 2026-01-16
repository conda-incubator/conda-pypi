# Mock Channel Server

The mock channel server is a local HTTP server that serves a conda channel with pre-packaged test data. This allows tests to run offline without requiring network access to conda-forge or PyPI.

## Overview

The mock channel server is located in `tests/conda_local_channel/` and provides:

- **Conda packages**: Pre-built `.conda` packages for common dependencies
- **Wheel files**: Python wheels that can be served directly from the channel
- **Repodata**: Channel metadata in `repodata.json` and `repodata.json.zst` formats
- **Multiple platforms**: Support for `linux-64`, `osx-arm64`, and `noarch` subdirectories

## Directory Structure

```
tests/conda_local_channel/
├── channeldata.json          # Channel-level metadata
├── index.html                # Human-readable channel index
├── linux-64/                 # Linux x86_64 packages
│   ├── python-*.conda
│   ├── *.conda               # Other conda packages
│   ├── repodata.json         # Package index
│   └── repodata.json.zst     # Compressed index
├── osx-arm64/                # macOS ARM64 packages
│   ├── python-*.conda
│   ├── *.conda
│   ├── repodata.json
│   └── repodata.json.zst
└── noarch/                   # Platform-independent packages
    ├── *.whl                 # Python wheels
    ├── repodata.json
    └── repodata.json.zst
```

## Using the Mock Channel Server

### In Tests

The mock channel server is available as a pytest fixture:

```python
def test_with_mock_channel(conda_local_channel):
    """Test using the mock conda channel."""
    # conda_local_channel is a URL like "http://localhost:8037"

    # Use it in your test
    channel_url = conda_local_channel
    # ... test code that uses the channel
```

The fixture automatically:
1. Starts an HTTP server on a port automatically 
2. Serves the `tests/conda_local_channel/` directory
3. Returns the server URL
4. Cleans up the server after the test completes

### Example: Testing Package Installation

```python
from conda.cli.main import main_subshell


def test_install_from_mock_channel(conda_local_channel, tmp_path):
    """Test installing a package from the mock channel."""
    env_prefix = tmp_path / "test_env"

    result = main_subshell(
        "create",
        "--prefix",
        str(env_prefix),
        "--channel",
        conda_local_channel,
        "--override-channels",
        "python=3.12",
        "requests",
    )

    assert result == 0
    assert (env_prefix / "bin" / "python").exists()
```

### Example: Testing Dependency Resolution

```python
def test_dependency_resolution(conda_local_channel):
    """Test that dependencies resolve correctly from mock channel."""
    from conda_pypi.convert_tree import ConvertTree

    # ConvertTree can use the mock channel for dependency resolution
    # This allows testing without network access
    pass
```

## Adding Packages to the Mock Channel

### Adding Conda Packages

To add new `.conda` packages to the mock channel:

1. Place the `.conda` file in the appropriate subdirectory (`linux-64`, `osx-arm64`, or `noarch`)
2. Update the channel index using `conda-index`

```bash
# From the project root
pixi run conda-index tests/conda_local_channel/
```

Or if you have `conda-index` available:

```bash
conda-index tests/conda_local_channel/
```

### Adding Wheel Files

The mock channel supports serving wheel files directly. To add a wheel:

1. **Place the wheel** in the `noarch/` directory:

```bash
cp package-1.0.0-py3-none-any.whl tests/conda_local_channel/noarch/
```

2. **Update the repodata.json** to include wheel metadata. The repodata format for wheels includes a `packages.whl` section:

```json
{
  "packages.whl": {
    "package-1.0.0-py3-none-any.whl": {
      "record_version": 3,
      "name": "package",
      "version": "1.0.0",
      "build": "py3_0",
      "build_number": 0,
      "depends": [
        "python >=3.8"
      ],
      "fn": "package-1.0.0-py3-none-any.whl",
      "sha256": "<sha256-hash>",
      "size": 12345,
      "subdir": "noarch",
      "timestamp": 1234567890,
      "noarch": "python"
    }
  }
}
```

3. **Regenerate the index**:

```bash
pixi run conda-index tests/conda_local_channel/
```

### Current Test Packages

The mock channel currently includes:

**Platform Packages (linux-64, osx-arm64)**:
- Python 3.12
- Core dependencies: `bzip2`, `libexpat`, `libffi`, `libsqlite`, `libzlib`, `ncurses`, `openssl`, `readline`, `tk`, `tzdata`
- Python tools: `pip`, `setuptools`, `wheel`

**Noarch Wheels**:
- `requests`: HTTP library for testing network-dependent code
- `fastapi`: Web framework for testing API conversions
- `pydantic`: Data validation for testing metadata
- `abqpy`: Package with specific dependency requirements
- And more...

## Implementation Details

### Wheel Support in Repodata

`conda-pypi` extends conda's repodata format to support wheel files. The repodata includes a `packages.whl` section alongside the standard `packages` and `packages.conda` sections:

```json
{
  "info": {
    "subdir": "noarch"
  },
  "packages": {},
  "packages.conda": {},
  "packages.whl": {
    "package-name.whl": { ... }
  }
}
```

This allows the conda solver to consider wheels during dependency resolution.

## Maintenance

### Updating Packages

When updating test packages:

1. **Update the package files**: Replace or add new `.conda` or `.whl` files
2. **Regenerate indexes**: Run `conda-index` on the channel directory
3. **Verify tests pass**: Run the test suite to ensure nothing broke
4. **Commit changes**: Include both the package files and updated repodata

### Keeping Packages Small

To keep the test suite fast and the repository small:

- Use minimal packages when possible
- Consider using package "stubs" with minimal actual content
- Compress large packages
- Only include packages that are actually used in tests

### Platform Considerations

The mock channel includes packages for multiple platforms:

- **linux-64**: Used in CI and Linux development
- **osx-arm64**: Used for Apple Silicon development
- **noarch**: Platform-independent packages (wheels and pure Python)

Ensure packages exist for the platforms where tests will run, or make tests platform-conditional.

## Troubleshooting

### Package Not Found

**Problem**: Tests fail because a package can't be found in the mock channel

**Solution**:
1. Verify the package exists in the appropriate subdirectory
2. Check that `repodata.json` includes the package
3. Regenerate the index with `conda-index`
4. Ensure the test is using `--override-channels` to force using the mock channel

### Metadata Mismatch

**Problem**: Package installs but with wrong dependencies

**Solution**:
- Verify the `repodata.json` has correct dependency information
- Check that the package metadata matches the actual package contents
- Regenerate the index to ensure consistency

## Best Practices

1. **Keep it minimal**: Only add packages that are actually needed for tests
2. **Document additions**: When adding packages, document why they're needed
3. **Regenerate indexes**: Always run `conda-index` after modifying packages
4. **Test offline**: Ensure tests can run without network access
5. **Version pin sparingly**: Only pin versions when necessary for test stability

## Related

- [Testing Guide](index.md): Overall testing documentation
- [pytest-xprocess](https://github.com/pytest-dev/pytest-xprocess): Plugin for managing test processes
- [conda-index](https://github.com/conda/conda-index): Tool for generating channel indexes
