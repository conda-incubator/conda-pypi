# Key differences between conda and PyPI

Below, we'll go over the two key differences between conda and PyPI packaging and why
this leads to issues for users. The first problem is related to how binary distributions
are packaged and distributed and the second problem is related to the package index
and how each tool tracks what is currently installed.

## Summary

- Conda and PyPI use different strategies for building binary distributions; when
  using these packaging formats together, it can lead to hard debug issues.
- PyPI tools are aware of what is installed in a conda environment but when these
  tools make changes to the environment conda looses track of what is installed.
- conda relies on all packaging metadata (available packages, their dependencies, etc)
  being available upfront. PyPI only lists the available packages, but their dependencies
  need to be fetched on a package-per-package basis. This means that the solvers are
  designed to work differently; a conda solver won't easily take the PyPI metadata
  because it is not designed to work iteratively.
- PyPI names are not always the same in a conda channel. They might have a different name,
  or use a different packaging approach altogether.

## Differences in binary distributions

Conda and PyPI are separate packaging ecosystems with different packaging formats and philosophies. Conda
distributes packages as `.conda` files, which can include Python libraries and pre-compiled
binaries with dynamic links to other dependencies. In contrast, PyPI mostly uses `.whl` files (colloquially
known as "wheels"), which typically bundle all required binaries or rely on system-level dependencies, as it
lacks support for non-Python dependency declarations.

With that in mind, what are some potential ways this could break when combining the two
ecosystems together? Because wheels typically include all of their pre-compiled binaries inside
the wheel itself, this can lead to incompatibilities when used with conda packages containing
pre-compiled binaries. In the conda ecosystem, these dependencies are normally tested with
each other before being published during the build process, but the PyPI ecosystem does not test
its wheels with conda packages and therefore users are typically the first one to run into these
errors.

Some examples of these incompatibilities include symbol errors, segfaults and other hard to debug
issues. Refer to the excellent [pypackaging-native key issues](https://pypackaging-native.github.io/#key-issues)
for even more information on this topic and specific examples.

## Differences in metadata concerning installed packages

The second relevant difference regarding how these two packaging ecosystems interact with
each other deals with how they track which packages are installed into an environment.
Inside conda environments, package metadata is saved in JSON files in a folder called
`conda-meta`. This serves as a way to easily identify everything that is currently installed
because each JSON file represents a package installed in that environment.

Tools using PyPI (e.g. `pip`) do not store metadata about the installed packages in single
location like `conda-meta`. Instead, they rely on the presence of `.dist-info` folders often
found directly next to the Python source code in the `lib/<python-version>/site-packages/`
directory.

The good thing is that conda Python packages will normally install this directory
when the package is installed. This means that `pip` installations on top of an existing
conda environment will be able to tell what is already installed and resolve its dependencies
relatively well. But, after you have installed something with `pip` in that environment,
conda no longer knows exactly what is installed because `pip` did not update the contents
of the `conda-meta` folder.

This ultimately means that conda begins to lose track of what is installed in a given environment.
Not only that, `pip` and `conda` can begin to overwrite what each has placed in the
`lib/<python-version>/site-packages` folder. The more you run each tool independently,
the more likely it is that this will happen, and the more this happens, the more unstable
and prone to errors this environment becomes.

## More on this topic

For an excellent overview of how Python packaging works:

- [Python Packaging - packaging.python.org](https://packaging.python.org/en/latest/overview/)

For an excellent overview of what a conda package actually is:

- [What is a conda package? - prefix.dev](https://prefix.dev/blog/what-is-a-conda-package)
