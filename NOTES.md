https://pypi.org/project/torch/#files

2.5.1 e.g., torch has only wheels, no sdists. Is called pytorch in conda-land.

LibMambaSolver (used to have) LibMambaIndexHelper.reload_local_channels() used
for conda-build, reloads all file:// indices.

(Can't figure out where this is used) See also reload_channel().

```
for channel in conda_build_channels:
    index.reload_channel(channel)
```

If we call the solver ourselves or if we use the post-solve hook, we could
handle "metadata but not package data converted" and generate the final .conda's
at that time. While generating repodata from the METADATA files downloaded
separately.

We could generate unpacked `<base env>/pkgs/<package>/` directories at the
post-solve hook and skip the `.conda` archive. Conda should think it has already
cached the new wheel -> conda packages.

In the twine example we wind up converting two versions of a package from wheel
to conda. One of them might have conflicted with the discovered solution.

Hash of a regular Python package is something like py312hca03da5_0

## Environment markers

Grab parameters from target Python; evaluate marker.

```python
some_environment = packaging.markers.default_environment()
packaging.markers.Marker("python_full_version=='3.12.4'").evaluate(
    environment=some_environment
)
```

`build`, which we use for tests uses environment markers, and extras.

corpus of metadata from pypi can be used to test marker evaluation.

## "arch" packages

Should be allowed.

## a little bit like conda-build

Build packages from wheels or sdists or checkouts, then keep them in the local
channel for later. (But what if we are in CI?)

## 'editable' command

Modern replacement for conda-build develop; works like pip install -e . --no-build-isolation
