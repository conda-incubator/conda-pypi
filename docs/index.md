# conda-pypi

Welcome to the `conda-pypi` documentation!

`conda-pypi` provides better PyPI interoperability for the conda ecosystem.
It allows you to safely install PyPI packages in conda environments by
converting them to conda format when possible, while falling back to
traditional pip installation when needed.

The tool offers two main commands: `conda pypi install` for safer PyPI
package installation with an intelligent hybrid approach, and `conda pypi
convert` for converting PyPI packages to `.conda` format without installing
them. The smart installation strategy ensures that explicitly requested
packages come from PyPI while dependencies are sourced from conda channels
when available.

`conda-pypi` includes full support for development workflows through
editable installations with the `-e` flag, and can install directly from git
repositories and local directories. To protect your conda environments, it
automatically deploys `EXTERNALLY-MANAGED` files to prevent accidental pip
usage that could break your environment's integrity.

:::{warning}
This project is still in early stages of development. Don't use it in
production (yet). We do welcome feedback on what the expected behaviour
should have been if something doesn't work!
:::

::::{grid} 2

:::{grid-item-card} 🏡 Getting started
:link: quickstart
:link-type: doc
New to `conda-pypi`? Start here to learn the essentials
:::

:::{grid-item-card} 💡 Motivation and vision
:link: why/index
:link-type: doc
Read about why `conda-pypi` exists and when you should use it
:::
::::

::::{grid} 2

:::{grid-item-card} 🍱 Features
:link: features
:link-type: doc
Overview of what `conda-pypi` can do for you
:::

:::{grid-item-card} 🏗️ Architecture
:link: developer/architecture
:link-type: doc
Technical architecture and plugin system design
:::

::::

::::{grid} 2

:::{grid-item-card} 📚 CLI Reference
:link: reference/cli-reference
:link-type: doc
Complete command-line interface documentation
:::

:::{grid-item-card} 🔧 Troubleshooting
:link: reference/troubleshooting
:link-type: doc
Common issues and how to resolve them
:::

:::{grid-item-card} 🔧 Developer Notes
:link: developer/developer-notes
:link-type: doc
Implementation details and technical insights
:::

::::

```{toctree}
:hidden:

quickstart
why/index
features
modules
changelog
developer/architecture
developer/developer-notes
reference/cli-reference
reference/troubleshooting
```
