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
conda pypi install package_name         # underscores instead of dashes

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

### Corporate firewall/proxy issues

**Problem**: Behind corporate firewall with proxy requirements.

**Solutions**:
```bash
# Configure pip proxy settings
export HTTP_PROXY=http://proxy.company.com:8080
export HTTPS_PROXY=http://proxy.company.com:8080

# For authenticated proxies
export HTTP_PROXY=http://username:password@proxy.company.com:8080

# Trust internal certificates
export PIP_TRUSTED_HOST=pypi.org,pypi.python.org,files.pythonhosted.org
```

### SSL/TLS certificate issues

**Problem**: Certificate verification failures.

**Error messages**:
- `SSL certificate verification failed`
- `Certificate verify failed`

**Solutions**:
```bash
# Temporarily disable SSL verification (not recommended for production)
export PIP_TRUSTED_HOST=pypi.org,pypi.python.org,files.pythonhosted.org

# Update certificates (macOS)
/Applications/Python\ 3.x/Install\ Certificates.command

# Update certificates (Linux)
sudo apt-get update && sudo apt-get install ca-certificates
```

## Getting Help

### Enable verbose output

For detailed debugging information:

```bash
# Basic verbose output
conda -v pip install package-name

# INFO level logging (repeat -v twice)
conda -v -v pip install package-name

# DEBUG level logging (repeat -v three times) - most useful for troubleshooting
conda -v -v -v pip install package-name

# TRACE level logging (repeat -v four times) - maximum detail
conda -v -v -v -v pip install package-name
```

### Preview operations

To see what would happen without making changes:

```bash
conda pypi install --dry-run package-name
conda pypi convert --dry-run package-name
```

### JSON output for scripts

For programmatic error handling:

```bash
conda pypi install --json package-name
```

## When to Seek Further Help

If you encounter issues not covered here:

1. **Check the version**: Ensure you're using the latest version of `conda-pypi`
2. **Search existing issues**: Check the [GitHub repository](https://github.com/conda-incubator/conda-pypi) for similar problems
3. **Provide details**: When reporting issues, include:
   - `conda-pypi` version (`conda list conda-pypi`)
   - Operating system and Python version
   - Complete error message with `-v` output
   - Minimal reproduction steps

Remember that `conda-pypi` is still in early development, so feedback about unexpected behavior is valuable for improving the tool.
