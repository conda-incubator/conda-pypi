import logging
import re

log = logging.getLogger(__name__)


def mocked_is_package_file(path):
    return path[-6:] == ".conda" or path[-8:] == ".tar.bz2" or path[-4:] == ".whl"


mocked_url_pat = re.compile(
    r"(?:(?P<url_p>.+)(?:[/\\]))?"
    r"(?P<fn>[^/\\#]+(?:\.tar\.bz2|\.conda|\.whl))"
    r"(?:#("
    r"(?P<md5>[0-9a-f]{32})"
    r"|((sha256:)?(?P<sha256>[0-9a-f]{64}))"
    r"))?$"
)


def add_whl_support() -> None:
    """Implement support for installing wheels in conda"""
    log.debug("Inside add_whl_support")

    # add .whl to KNOWN EXTENSIONS
    import conda.common.path

    conda.common.path.KNOWN_EXTENSIONS = (
        ".conda",
        ".tar.bz2",
        ".json",
        ".jlap",
        ".json.zst",
        ".whl",
    )

    # Patch the extract_tarball function
    # Add support for extracting wheels with in-line creation of conda metadata files
    import conda.core.path_actions
    from conda_pypi.pre_command.extract_whl_or_tarball import extract_whl_or_tarball

    conda.core.path_actions.extract_tarball = extract_whl_or_tarball

    # Allow the creation of prefix record JSON files for .whl files
    import conda.core.prefix_data

    conda.core.prefix_data.CONDA_PACKAGE_EXTENSIONS = (".tar.bz2", ".conda", ".whl")

    import conda.models.match_spec

    conda.models.match_spec.is_package_file = mocked_is_package_file

    import conda.misc

    conda.misc.url_pat = mocked_url_pat

    # Conda CLI/argparse uses MatchSpec to validate specs, causing specs to be
    # parsed (and cached) before the whl monkeypatching occurs.
    # Clear cache after monkeypatching so subsequent MatchSpec usage
    # (e.g., in Environment.from_cli) will parse the spec correctly.
    conda.models.match_spec._PARSE_CACHE.clear()

    # TODO
    # There is some extension handling taking place in `conda.models.match_spec.MatchSpec.from_dist_str``
    # that we might need to patch
    return
