# Features

`conda-pypi` uses the `conda` plugin system to implement several features that make `conda` integrate better with the PyPI ecosystem:

## The `conda pip` subcommand

This new subcommand wraps `pip` (and/or other PyPI tools) so you can install PyPI packages (or their conda equivalents) in your conda environment in a safer way.

The main logic currently works like this:

1. Collect the PyPI requirements and execute `pip install --dry-run` to obtain a JSON report of "what would have happened".
2. The JSON report is parsed and the resolved dependencies are normalized and mapped to the configured conda channels via different sources (e.g. `cf-graph-countyfair`, `grayskull`, `parselmouth`).
3. The packages that were found on the configured conda channels are installed with `conda`. Those _not_ on conda are installed individually with `pip install --no-deps`.

:::{admonition} Coming soon
:class: seealso

Right now we are not disallowing compiled wheels, but we might add options in the future to only allow pure Python wheels via `whl2conda`.
:::

(pypi-lines)=

## `conda list` integrations

`conda` has native support for listing PyPI dependencies as part of `conda list`. However, this is not enabled in all output modes. `conda list --explicit`, used sometimes as a lockfile replacement, does not include any information about the PyPI dependencies.

We have added a post-command plugin to list PyPI dependencies via `# pypi:` comments. This is currently an experimental, non-standard extension of the file format subject to change. The syntax is:

```
# pypi: <name>[==<version>] [--python-version str] [--implementation str] [--abi str ...] [--platform str ...] [--record-checksum <algorithm>=<value>]
```

All fields above should be part of the same line. The CLI mimics what `pip` currently accepts (as
of v24.0), with the exception of `--record-checksum`, which is a custom addition.
`--record-checksum` is currently calculated like this:

1. Given a `RECORD` file, we parse it as a list of 3-tuples: path, hash and size.
2. We skip `*.dist-info` files other than `METADATA` and `WHEEL`.
3. For non site-packages files, we only keep the path for those than fall in `bin`, `lib`
   and `Scripts` because their hash and size might change with path relocation.
4. The list of tuples `(path, hash, size)` is then sorted and written as a JSON string with no
   spaces or indentation.
5. This is written to a temporary file and then hashed with MD5 or SHA256.

## `conda install` integrations

Another post-command plugin is also available to process `@EXPLICIT` lockfiles and search for `# pypi:` lines as discussed above. Again, this is experimental and subject to change.

## `conda env` integrations

:::{admonition} Coming soon
:class: seealso

`environment.yml` files famously allow a `pip` subsection in their `dependencies`. This is handled internally by `conda env` via a `pip` subprocess. We are adding new plugin hooks so `conda-pypi` can handle these in the same way we do with the `conda pip` subcommand.
:::

(externally-managed)=

## Environment marker files

`conda-pypi` adds support for [PEP-668](https://peps.python.org/pep-0668/)'s [`EXTERNALLY-MANAGED`](https://packaging.python.org/en/latest/specifications/externally-managed-environments/) environment marker files.

This file will tell `pip` and other PyPI installers to not install or remove any packages in that environment, guiding the user towards a safer way of achieving the same result. In our case, the message will let you know that a `conda pip` subcommand is available (see above).

With this file we mostly want to avoid accidental overwrites that could break your environment. You can still use `pip` directly if you want, but you'll need to add the `--break-system-packages` flag.
