import logging
import re
from conda.base.context import context
from conda.base.constants import CONDA_PACKAGE_EXTENSION_V1, CONDA_PACKAGE_EXTENSION_V2

log = logging.getLogger(__name__)


def mocked_from_dist_str(cls, dist_str):
    parts = {}
    if dist_str[-len(CONDA_PACKAGE_EXTENSION_V2) :] == CONDA_PACKAGE_EXTENSION_V2:
        dist_str = dist_str[: -len(CONDA_PACKAGE_EXTENSION_V2)]
    elif dist_str[-len(CONDA_PACKAGE_EXTENSION_V1) :] == CONDA_PACKAGE_EXTENSION_V1:
        dist_str = dist_str[: -len(CONDA_PACKAGE_EXTENSION_V1)]
    elif dist_str[-4:] == ".whl":
        dist_str = dist_str[:-4]
    if "::" in dist_str:
        channel_subdir_str, dist_str = dist_str.split("::", 1)
        if "/" in channel_subdir_str:
            channel_str, subdir = channel_subdir_str.rsplit("/", 1)
            if subdir not in context.known_subdirs:
                channel_str = channel_subdir_str
                subdir = None
            parts["channel"] = channel_str
            if subdir:
                parts["subdir"] = subdir
        else:
            parts["channel"] = channel_subdir_str

    name, version, build = dist_str.rsplit("-", 2)
    parts.update(
        {
            "name": name,
            "version": version,
            "build": build,
        }
    )
    return cls(**parts)


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


def add_whl_support(command: str) -> None:
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

    if conda.core.path_actions.extract_tarball.__module__ != __name__:
        from conda_pypi.pre_command.extract_whl_or_tarball import extract_whl_or_tarball

        conda.core.path_actions.extract_tarball = extract_whl_or_tarball

    # Allow the creation of prefix record JSON files for .whl files
    import conda.core.prefix_data

    conda.core.prefix_data.CONDA_PACKAGE_EXTENSIONS = (".tar.bz2", ".conda", ".whl")

    # Skip the check that name, version, build matches filename in prefix record json
    from conda.core.prefix_data import PrefixData

    if PrefixData._load_single_record.__module__ != __name__:
        from conda_pypi.pre_command.patched_load import _load_single_record

        PrefixData._load_single_record = _load_single_record

    import conda.models.match_spec

    conda.models.match_spec.is_package_file = mocked_is_package_file

    import conda.misc

    conda.misc.url_pat = mocked_url_pat

    # import conda.models.match_spec
    # conda.models.match_spec.MatchSpec.from_dist_str = mocked_from_dist_str
    return
