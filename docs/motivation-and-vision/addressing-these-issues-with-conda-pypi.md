# Addressing these Issues with conda-pypi

So far, we have outlined why these packaging ecosystems do not always work together
well and a couple strategies users have used in the past to overcome them. How exactly
does the `conda-pypi` plugin plan on addressing them? Below are a couple of methods 
we've discussed to address these issues.

## On-the-fly conversion of PyPI wheels to conda packages

The inspiration for this approach initially started with the [conda-pupa](https://github.com/dholth/conda-pupa)
project. The philosophy used here is that we can simply convert a wheel from PyPI into a conda
package and cache it on the host locally. In conda, it's quite easy to configure multiple channels
to be used when installing packages, and by default, a "local" channel is included. As `conda-pypi`
is run, it will begin transforming and caching wheels from PyPI into the conda pacakges which
are then saved in this local channel.

This is the approach we currently feel most confident with implementing.

## Analyze the dependency tree of your PyPI package

In this approach, we run `pip` with the `--dry-run` option and analyze the proposed solution. Of those packages,
we see which ones are already available on the configured conda channels and install them with `conda` proper.
For the ones that are not available, we pass them to `pip install --no-deps` and hope for an ABI compatible setting.

This was an approach we initially tried but then gave up in favor for the "conda-pupa" approach.
