conda-pupa
==========

/ˈpjuː.pə/, plural /ˈpjuː.piː/

Convert PyPA package "caterpillers", whether they use `setup.py` or
`pyproject.toml`, to beautiful `.conda` butterflies.

"conda develop" but use pypa/build and convert the development wheel to a .conda
before install. Combine grayskull pypi, whl2conda, conda-pypi in a simpler
package. Index the outputs to a local channel then install.

See https://github.com/conda/schemas or maybe not - has no schema for paths.json
or index.json

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

Have 100% test coverage.
