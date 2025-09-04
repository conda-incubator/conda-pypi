# Troubleshooting

This guide covers the most common issues you may encounter when using `conda-pypi` and how to resolve them.

## Environment Issues

### Missing Python or pip requirements

**Problem**: `conda-pypi` fails with an error about missing Python or pip.

**Error messages**:
```
Target environment at /path/to/env requires python>=3.2
Target environment at /path/to/env requires pip>=23.0.1
```

**Solution**: Ensure your target environment has the required dependencies:

```bash
# Install required dependencies in your environment
conda install -n myenv python>=3.9 pip>=23.0.1

# Or when creating a new environment
conda create -n myenv python>=3.10 pip
```

### Invalid environment

**Problem**: Commands fail when specifying a non-existent environment.

**Error messages**:
- `environment does not exist`
- `python>=3.2 not found`

**Solution**:
```bash
# Check if environment exists
conda env list

# Create the environment if it doesn't exist
conda create -n myenv python=3.10 pip

# Use correct environment name or path
conda pypi install -n myenv package-name
```

## Package Resolution Issues

### Package not found on PyPI

**Problem**: Package doesn't exist or has a different name on PyPI.

**Error messages**:
- `No matching distribution found`
- `Could not find a version that satisfies the requirement`
- `404 Client Error`

**Solutions**:
```bash
# Check package name on PyPI
pip search package-name  # or visit pypi.org

# Try common name variations
conda pypi install python-package-name  # instead of package-name
```

### Dependency resolution timeout

**Problem**: Complex dependency trees exceed the solver's retry limit.

**Error messages**:
- `Exceeded maximum of 20 attempts`
- `Could not resolve dependencies after 20 attempts`

**Solutions**:
```bash
# Use --override-channels to simplify resolution
conda pypi install --override-channels package-name

# Install dependencies from conda first
conda install numpy pandas scipy
conda pypi install your-package

# Try installing packages individually
conda pypi install package1
conda pypi install package2
```

### Conflicting dependencies

**Problem**: Package requirements conflict with existing environment.

**Solutions**:
```bash
# Preview what would be installed
conda pypi install --dry-run package-name

# Check existing packages
conda list

# Create a fresh environment for testing
conda create -n test python=3.10 pip
conda activate test
conda pypi install package-name
```

## Network and Connectivity Issues

### PyPI connectivity problems

**Problem**: Cannot connect to PyPI servers.

**Error messages**:
- `Connection timeout`
- `Failed to establish connection`
- `Name resolution failed`

**Solutions**:
```bash
# Test basic connectivity
ping pypi.org

# Try with verbose output to see connection details
conda -v pip install package-name

# Check conda's network configuration
conda config --show channels
```

## Getting Help

### Enable verbose output

For detailed debugging information:

```bash
# Basic verbose output
conda -v pip install package-name

# INFO level logging (repeat -v twice)
conda -vv pip install package-name

# DEBUG level logging (repeat -v three times) - most useful for troubleshooting
conda -vvv pip install package-name

# TRACE level logging (repeat -v four times) - maximum detail
conda -vvvv pip install package-name
```

## When to Seek Further Help

If you encounter issues not covered here:

1. **Check the version**: Ensure you're using the latest version of `conda-pypi`
2. **Search existing issues**: Check the [GitHub repository](https://github.com/conda-incubator/conda-pypi) for similar problems
3. **Report issues**: When reporting issues please to include all the relevant details

Remember that `conda-pypi` is still in early development, so feedback about unexpected behavior is valuable for improving the tool.
