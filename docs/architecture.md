# Architecture

This page documents the technical architecture of `conda-pypi`, explaining
how it integrates with conda and the internal organization of its components.

## Plugin System Integration

`conda-pypi` is implemented as a conda plugin using conda's official plugin
architecture. This design enables seamless integration with conda's existing
workflows without requiring modifications to conda itself.

The plugin registers several hooks with conda's plugin system. The
subcommand hook adds the `conda pypi` subcommand to conda through
`conda_pypi.plugin.conda_subcommands()`, providing both `conda pypi install`
for installing PyPI packages with conversion and `conda pypi convert` for
converting PyPI packages without installing them.

The plugin also registers a post-command hook that extends conda's existing
commands. The environment protection hook triggers after `install`, `create`,
`update`, and `remove` commands to automatically deploy `EXTERNALLY-MANAGED`
files that prevent accidental pip usage. This is implemented through
`ensure_target_env_has_externally_managed()`.

## Module Architecture

The codebase is organized into focused modules, each with specific
responsibilities:

### Core Modules

#### `plugin.py` - Plugin Entry Point
- **Role**: Conda plugin registration and hook implementations
- **Key Functions**:
  - Register `conda pypi` subcommand
  - Register post-command hook for EXTERNALLY-MANAGED deployment
  - Coordinate with conda's plugin system

#### `cli.py` - Command Line Interface
- **Role**: Argument parsing and command execution for `conda pypi`
- **Key Functions**:
  - `configure_parser()` - Set up CLI argument structure
  - `execute_install()` - Handle `conda pypi install` logic
  - `execute_convert()` - Handle `conda pypi convert` logic
- **Architecture**: Clean separation between CLI concerns and core logic

#### `core.py` - High-Level Operations
- **Role**: Main orchestration layer for package conversion and installation
- **Key Functions**:
  - `convert_packages()` - Convert packages without dependencies
  - `convert_packages_with_dependencies()` - Full dependency resolution and conversion
  - `prepare_packages_for_installation()` - Prepare packages for conda installation
  - `install_packages()` - Execute conda installation
- **Dependencies**: Coordinates between solver, builder, utils, and VCS
  modules

### Specialized Modules

#### `solver.py` - Dependency Resolution
- **Role**: Intelligent dependency resolution using conda's solver
- **Key Components**:
  - `PyPIDependencySolver` - Iterative dependency resolution
  - `ReloadingLibMambaSolver` - Enhanced conda solver wrapper
- **Algorithm**:
  1. Attempt conda solve with current packages
  2. Parse solver errors to identify missing packages
  3. Fetch missing packages from PyPI
  4. Convert to conda format
  5. Repeat until all dependencies resolved

#### `builder.py` - Package Conversion Engine
- **Role**: Convert Python wheels to conda packages using integrated
  conversion functionality
- **Key Components**:
  - `build_conda()` - Main wheel-to-conda conversion
  - `build_pypa()` - Build conda packages from Python projects
  - `CondaMetadata` - Metadata translation utilities
- **Capabilities**:
  - Python metadata to conda format translation
  - Cross-platform package building
  - Dependency mapping and normalization

#### `utils.py` - Utilities and Helpers
- **Role**: Common utilities used across the codebase
- **Key Areas**:
  - PyPI package fetching and downloading
  - Python executable detection
  - Environment path management
  - Package name normalization
  - `EXTERNALLY-MANAGED` file management
- **Design**: Consolidated utility functions to avoid code duplication

#### `mapping.py` - Package Name Mapping
- **Role**: Map PyPI package names to conda equivalents
- **Key Functions**:
  - `pypi_to_conda_name()` - Convert PyPI names to conda names
  - `conda_to_pypi_name()` - Reverse mapping
  - `get_grayskull_mapping()` - Load automated mapping data
- **Data Sources**: Uses grayskull project mappings for automated name
  translation

#### `vcs.py` - Version Control Integration
- **Role**: Handle VCS URLs for editable installations
- **Key Components**:
  - `VCSHandler` - Support for git, hg, svn, bzr
  - `VCSInfo` - VCS URL parsing and metadata
- **Capabilities**:
  - Parse VCS URLs with branches, refs, subdirectories
  - Clone repositories for editable installs
  - Support multiple VCS systems

#### `main.py` - Environment Management
- **Role**: Environment validation and lockfile functionality
- **Key Functions**:
  - `validate_target_env()` - Check environment requirements
  - `pypi_lines_for_explicit_lockfile()` - Generate PyPI lockfile lines
  - Environment compatibility checking

#### `exceptions.py` - Error Handling
- **Role**: Define conda-pypi specific exceptions
- **Components**: Custom exception classes that integrate with conda's error
  system

## Data Flow Architecture

### Installation Flow

```
conda pypi install package
         ↓
CLI Argument Parsing
         ↓
Environment Validation
         ↓
Package Classification
         ↓
    VCS/Editable? ----Yes---→ Direct pip install
         ↓ No
Dependency Resolution
         ↓
Channel Search for Dependencies
         ↓
Convert Missing from PyPI
         ↓
Install via conda
         ↓
Deploy EXTERNALLY-MANAGED
```

### Conversion Flow

```
conda pypi convert package
         ↓
Fetch from PyPI
         ↓
Download Wheels
         ↓
Convert to .conda
         ↓
Save to Output Directory
```

### Plugin Hook Flow

```
conda command executed
         ↓
Post-command hook?
         ↓
install/create/update/remove
         ↓
      Deploy
   EXTERNALLY-
     MANAGED
         ↓
   Create marker
      files
```

## Key Design Principles

The architecture of `conda-pypi` is built around several key design
principles that ensure effective integration between conda and PyPI
ecosystems.

Conda-native integration is achieved by using conda's official plugin
system and leveraging conda's existing infrastructure including solvers,
channels, and metadata systems. This approach maintains full compatibility
with existing conda workflows.

The system emphasizes modularity and separation of concerns with clear
separation between CLI, core logic, and specialized functionality. Each module
has a focused responsibility with minimal coupling between modules, making the
codebase easier to maintain and extend.

The intelligent hybrid approach ensures that explicit packages always come
from PyPI to respect user intent, while dependencies prefer conda channels
for ecosystem compatibility. The system falls back to PyPI conversion only
when needed.

Extensibility is built into the design through the plugin architecture that
allows easy extension, modular design that supports new conversion engines,
and VCS system support that can be easily extended to new version control
systems.

Error resilience is maintained through graceful handling of conversion
failures, continuing to process other packages when one fails, and providing
clear error reporting and debugging information.

This architecture enables conda-pypi to provide a seamless bridge between
the conda and PyPI ecosystems while maintaining the integrity and benefits of
both package management systems.
