# Motivation and vision

You might be wondering _why_ `conda-pypi` exists. Why you need to install and use it, or even if you should. Even if you already did that, what should you expect? What is it recommended and what is discouraged? In this page we will gather our motivation and vision for this tool.

## Why?

Mixing conda and PyPI packaging and tooling is often discouraged in the conda ecosystem. But why?
This is mostly due to the following default behaviors:

- **`pip` will overwrite packages installed by `conda`**. When you run `pip` within a conda environment, it doesn't know anything about conda packages. All it sees is a Python installation with several packages under `site-packages`. If the user requests a package that is not installed, it will happily proceed. This might need updating some dependencies that were initially installed by conda. pip will successfully finish that operation, but conda won't be notified of the new changes. The conda metadata is now incorrect (e.g. the versions reported by `conda list` are wrong).
- **Compiled wheels are often incompatible with conda packages**. If the wheels you are installing contained compiled extensions, you will end up running into problems. Maybe you were lucky the first few times, but at some point you won't and all you'll have left is a broken conda environment that needs to be recreated. Some examples include symbol errors, segfaults and other hard to debug issues. Refer to the excellent [pypackaging-native key issues](https://pypackaging-native.github.io/#key-issues) for all the information you will ever need about this topic.

:::{admonition} Safe conda & pip patterns
:class: info

There are only a handful of patterns that are considered safe:

- **Only Python & pip environments**: `conda` only provides `python` and `pip`.
  All other packages are _always_ installed with `pip`:

  ```console
  $ conda create -n pip-environment python=3.10 pip
  $ conda activate pip-environment
  $ pip install ...
  ```

- **Editable installs**: `conda` provides all the dependencies of a given package.
  Then that package is installed on top in editable mode, without addressing dependencies
  to make sure we don't accidentally overwrite conda files:

  ```console
  $ git clone git@github.com:owner/package.git
  $ conda create -n editable-install package --deps-only
  $ conda activate editable-install
  $ pip install -e . --no-deps
  ```
:::

These two things combined are dangerous, but still, sometimes it works! Maybe no files were overwritten, and maybe the compiled bits don't overlap. This lets people believe that is generally safe to do, while in reality they have been enjoying a lucky streak for a while. So, what should people do instead?

- **Package your PyPI dependencies as conda packages**. This will ensure maximum compatibility with the conda ecosystem, by design. You'll probably want to run `grayskull` to generate a recipe out of the PyPI project, and then open a PR in `conda-forge/staged-recipes`. Of course, this has maintenance costs and not everyone can afford to invest that much time in a dependency of the project. Sadly, this might be the only solution if the dependency includes compiled extensions with complicated dependencies.
- **Analyze the dependency tree of your PyPI package and install things with `conda`**. The idea
is to run a `--dry-run` install of the PyPI package and analyze the proposed solution. Of those packages, see which ones are already available on the configured conda channels and install them with `conda` proper. The ones that are not, pass them to `pip install --no-deps` and hope for an ABI compatible setting.

Are we expecting you to do all that manually? Of course not! This is what `conda-pypi` will help you achieve, among other things.

## The vision

`conda-pypi` aims to provide a safer experience with the conda and PyPI ecosystems. We'd like to see this tool an opt-in way to:

- Protect the user from accidental papercuts and difficult-to-undo operations.
- Educate about best practices via the included tooling.
- Allow `pip` and other PyPI installers to interact with conda environments in a non-disruptive way.

## Expected behavior

Refer to the [Quick start guide](quickstart.md).
