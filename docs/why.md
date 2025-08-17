# Motivation and vision

You might be wondering _why_ `conda-pypi` exists. Why you need to install
and use it, or even if you should. Even if you already did that, what should
you expect? What is it recommended and what is discouraged? In this page we
will gather our motivation and vision for this tool.

## Why?

Mixing conda and PyPI packaging and tooling is often discouraged in the
conda ecosystem, primarily due to two significant compatibility issues.

First, `pip` will overwrite packages installed by `conda` because when you
run pip within a conda environment, it doesn't know anything about conda
packages. All it sees is a Python installation with several packages under
`site-packages`. If you request a package that is not installed, pip will
happily proceed and might update some dependencies that were initially
installed by conda. While pip will successfully finish the operation, conda
won't be notified of these changes, leaving the conda metadata incorrect with
versions reported by `conda list` being wrong.

Second, compiled wheels are often incompatible with conda packages. If the
wheels you're installing contain compiled extensions, you will likely run into
problems. You might be lucky the first few times, but eventually you'll end
up with a broken conda environment that needs to be recreated. Common issues
include symbol errors, segfaults, and other hard-to-debug problems. For
comprehensive information about these issues, refer to the excellent
[pypackaging-native key issues](https://pypackaging-native.github.io/#key-issues)
documentation.

:::{admonition} Safe conda & pip patterns
:class: info

There are only a handful of patterns that are considered safe.

The first safe pattern is using "Only Python & pip environments" where
`conda` only provides `python` and `pip`, and all other packages are always
installed with `pip`. This approach looks like creating an environment with
`conda create -n pip-environment python=3.10 pip`, activating it with `conda
activate pip-environment`, and then using `pip install` for everything else.

The second safe pattern involves "Editable installs" where `conda` provides
all the dependencies of a given package, and then that package is installed
on top in editable mode without addressing dependencies to ensure we don't
accidentally overwrite conda files. This typically involves cloning a
repository, creating a conda environment with `conda create -n
editable-install package --deps-only`, activating the environment, and then
running `pip install -e . --no-deps`.
:::

These compatibility issues can be dangerous, though sometimes mixing conda
and pip appears to work. This happens when no files are overwritten and the
compiled components don't overlap, leading people to believe it's generally
safe when they've actually been enjoying a lucky streak.

What should people do instead? There are two traditional approaches. The
first is packaging your PyPI dependencies as conda packages, which ensures
maximum compatibility with the conda ecosystem by design. You'll probably
want to run `grayskull` to generate a recipe out of the PyPI project and then
open a PR in `conda-forge/staged-recipes`. However, this has maintenance
costs that not everyone can afford, and might be the only solution if the
dependency includes compiled extensions with complicated dependencies.

The second approach involves analyzing the dependency tree of your PyPI
package and installing things with `conda` where possible. The idea is to run
a `--dry-run` install of the PyPI package and analyze the proposed solution.
Of those packages, you would see which ones are already available on the
configured conda channels and install them with `conda` directly. The
packages that are not available would then be passed to `pip install
--no-deps`, hoping for an ABI compatible setting.

Are we expecting you to do all that manually? Of course not! This is
exactly what `conda-pypi` does for you automatically.

## How conda-pypi solves these problems

`conda-pypi` addresses the conda-PyPI compatibility issues through several
key innovations that automate the manual processes described above.

### Intelligent Package Conversion
Instead of installing PyPI packages directly, `conda-pypi` converts them to
native `.conda` format using its integrated conversion engine. This ensures
full conda compatibility where converted packages work seamlessly with
conda's dependency resolver. Package information is correctly tracked in
conda's database, and converted packages follow conda's file layout
conventions to avoid conflicts.

### Hybrid Installation Strategy
`conda-pypi` uses a sophisticated approach that respects user intent while
maximizing conda compatibility. Packages you explicitly request are always
converted from PyPI to ensure you get exactly what you asked for.
Dependencies are preferentially installed from conda channels when available,
with an intelligent fallback that only converts dependencies from PyPI when
they're not available on conda channels. Direct pip installation is used only
when necessary, such as for editable VCS installs.

### Environment Protection
The system automatically prevents accidental direct pip usage through
EXTERNALLY-MANAGED markers. All installations are properly recorded in
conda's metadata, and operations are reversible so installations can be
cleanly removed with conda.

## The vision

`conda-pypi` aims to provide a safer experience with the conda and PyPI
ecosystems through an opt-in solution that protects users from accidental
papercuts and difficult-to-undo operations. The tool educates about best
practices through clear messaging and safer defaults while enabling pip
compatibility and maintaining conda environment integrity.

Ultimately, the goal is to bridge the two ecosystems by making PyPI
packages first-class citizens in conda environments, allowing users to
leverage the best of both package management systems without the traditional
compatibility risks.

## Expected behavior

Refer to the [Quick start guide](quickstart.md).
