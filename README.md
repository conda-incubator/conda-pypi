"conda develop" but use pypa/build and convert the development wheel
to a .conda before install. Combine grayskull pypi, whl2conda,
conda-pypi in a simpler package. Index the outputs to a local channel
then install.

See https://github.com/conda/schemas or maybe not - has no schema for paths.json or index.json
