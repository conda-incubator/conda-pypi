# Architecture

This page documents the technical architecture of `conda-pypi`, explaining
how it integrates with conda and the internal organization of its components.

## Plugin System Integration

`conda-pypi` is implemented as a conda plugin using `conda`'s official plugin
architecture. This design enables seamless integration with conda's existing
workflows without requiring modifications to conda itself.

The plugin registers several hooks with `conda`'s plugin system. The
subcommand hook adds the `conda pypi` subcommand to conda through
`conda_pypi.plugin.conda_subcommands()`, providing both `conda pypi install`
for installing PyPI packages with conversion and `conda pypi convert` for
converting PyPI packages without installing them.

The plugin also registers three post-command hooks that extend conda's
existing commands. The environment protection hook triggers after `install`,
`create`, `update`, and `remove` commands to automatically deploy
`EXTERNALLY-MANAGED` files that prevent accidental `pip` (or any other Python install tool) usage. This is
implemented through `ensure_target_env_has_externally_managed()`.

The explicit lockfile hook activates after `conda list --explicit` commands
to add PyPI package information as comments to explicit lockfiles. The
implementation in `_post_command_list_explicit()` appends `# pypi:` comment
lines to lockfile output.

Finally, the PyPI lines processing hook triggers after `conda install` and
`conda create` commands to automatically process PyPI lines found in
lockfiles during environment creation or installation. This is handled by
`_post_command_process_pypi_lines()`.

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
    ↓        ↓           ↓
list      install/    install/create/
--explicit  create     update/remove
    ↓        ↓           ↓
Add PyPI  Process    Deploy
lines     PyPI       EXTERNALLY-
    ↓     lines      MANAGED
Output to   ↓           ↓
stdout   Install    Create marker
         PyPI       files
         packages
```

## Key Design Principles

The architecture of `conda-pypi` is built around several key design
principles that ensure effective integration between conda and PyPI
ecosystems.

Conda-native integration is achieved by using `conda`'s official plugin
system and leveraging `conda`'s existing infrastructure including solvers,
channels, and metadata systems. This approach maintains full compatibility
with existing conda workflows.

The system emphasizes modularity and separation of concerns with clear
separation between CLI, core logic, and specialized functionality. Each module
has a focused responsibility with minimal coupling between modules, making the
codebase easier to maintain and extend.

This hybrid approach ensures that explicit packages always come
from PyPI to respect user intent, while dependencies prefer conda channels
for ecosystem compatibility. The system falls back to PyPI conversion only
when needed.

This architecture enables conda-pypi to provide a seamless bridge between
the conda and PyPI ecosystems while maintaining the integrity and benefits of
both package management systems.
