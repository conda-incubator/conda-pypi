🐛 conda-pupa 🦋
===============

/ˈpjuː.pə/, plural /ˈpjuː.piː/

Convert PyPA package "caterpillers", whether they use `setup.py` or
`pyproject.toml`, to beautiful `.conda` butterflies.

`conda-pupa` is handy for filling in a handful of [PyPI](https://pypi.org) exclusive dependencies in your `conda` environment. You can share the resulting packages with other `conda` users even if they are not using `conda-pupa`.

`conda-pupa` is the easiest way to build a Python project as a `conda` package without using `conda-build` or a separate recipe.

`conda-pupa` replaces `pip install -e .`, but `conda` treats the Python package the same as any other `conda` package, because it is a `conda` package, and it can use dependencies from `conda`. It is a Python-standards way to replace the simplistic `conda-build develop`; `conda-pupa` understands `pyproject.toml` as well as `setup.py`.

Vision
======

Install pypi projects into conda environments, converting them all to `.conda`
on the fly before using `conda` to do the installation.

Recursively add missing pypi packages into the conda environment, in the same
way that "pip wheel <package>" populates a directory with `.whl` packages of it
and all of its dependencies.

Control which packages are built from pypi and cached versus which come from
pre-existing conda channels.

Replace `conda-build develop` with something compatible with all modern Python
projects, more like `pip install -e .`

Use Python standards to build packages, handle metadata for both `setup.py`,
`pyproject.toml`. Glue together libraries to process packages and their metadata.

- [build](https://github.com/pypa/build)
- [importlib.metadata](https://docs.python.org/3/library/importlib.metadata.html)
- [installer](https://github.com/pypa/installer)
- [packaging](https://github.com/pypa/packaging)
- [unearth](https://unearth.readthedocs.io/en/latest/)

Have 100% test coverage.

Installation
============

`conda-pupa` depends on `conda`. It provides a `conda` plugin for use without having to install into the active environment. To make it available to the main conda,

`conda install -n base -c dholth conda-pupa`

Alternatively, `python -m conda_pupa`.

Usage
=====

`conda-pupa` works on environments that already contain `python`.

```conda pupa -e .```

> Create and install a `conda` package linking a `pyproject.toml` or `setup.py` project at `.` into the Python environment, like `pip install -e .`

---
```conda pupa --build .```

> Build a wheel for a Python project and convert to `.conda`.

---
```conda pupa --prefix $CONDA_PREFIX twine==6.0.1```

> If a dependency `twine==6.0.1`, passed as a conda-format MatchSpec, is missing from `$CONDA_PREFIX`, then convert it and its dependencies from pypi wheels to conda packages. Collect the new `.conda` packages into a local channel.
>
> Add `--override-channels` to convert all dependencies missing from `--prefix` from `pypi` and not just the ones missing from your default conda channels.
>
> 🐞 Note `conda-pupa` currently packages all wheels as `noarch` even if they should be arch-specific.

```
% conda pupa --help
Usage: conda pupa [OPTIONS] [PACKAGE_SPEC]...

Options:
  -c, --channel TEXT            Additional channel to search for packages.
  -O, --override-channels TEXT  Do not search default or .condarc channels.
                                Will search pypi.
  -e, --editable TEXT           Build named path as editable package; install
                                to link checkout to environment.
  -b, --build TEXT              Build named path as wheel converted to conda.
  -p, --prefix TEXT             Full path to environment location (i.e.
                                prefix).
  -n, --name TEXT               Name of environment.
  -h, --help                    Show this message and exit.
  ```

  Bugs
  ====

- `conda-pupa` does not have optimizations.
- `conda-pupa` packages all packages as `noarch` even if they should be platform specific; this works okay for local single-platform use.
- `conda-pupa` does not consider Python [extras](https://packaging.python.org/en/latest/tutorials/installing-packages/#installing-extras).
- ... and more!

Future Improvements
===================

- When available, convert `pypi` metadata files only to generate `repodata.json` during dependency discovery, like pip. Once a solution has been found, download and convert the necessary wheels.
- Use conda's build hash to tag wheels that may convert to more than one `conda` package in case of Python [markers](https://packaging.pypa.io/en/stable/markers.html).
- Handle Python source distributions. Use conda to install the compiler too?
- ...