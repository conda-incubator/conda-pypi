from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from conda import plugins

if TYPE_CHECKING:
    from typing import Generator


log = logging.getLogger(__name__)

def add_whl_support(command: str) -> None:
    """ Implement support for installing wheels in conda """
    log.debug("Inside add_whl_support")

    # add .whl to KNOWN EXTENSIONS
    import conda.common.path
    conda.common.path.KNOWN_EXTENSIONS = (".conda", ".tar.bz2", ".json", ".jlap", ".json.zst", ".whl")

    # Patch the extract_tarball function
    # Add support for extracting wheels with in-line creation of conda metadata files
    import conda.core.path_actions
    if conda.core.path_actions.extract_tarball.__module__ != __name__:
        from .extract_whl_or_tarball import extract_whl_or_tarball
        conda.core.path_actions.extract_tarball = extract_whl_or_tarball

    # Allow the creation of prefix record JSON files for .whl files
    import conda.core.prefix_data
    conda.core.prefix_data.CONDA_PACKAGE_EXTENSIONS = (".tar.bz2", ".conda", ".whl")

    # Skip the check that name, version, build matches filename in prefix record json
    from conda.core.prefix_data import PrefixData
    if PrefixData._load_single_record.__module__ != __name__:
        from .patched_load import _load_single_record
        PrefixData._load_single_record = _load_single_record

    return


@plugins.hookimpl
def conda_pre_commands() -> Generator[plugins.CondaPreCommand, None, None]:
    yield plugins.CondaPreCommand(
        name="conda-whl-support",
        action=add_whl_support,
        run_for={
            "create",
            "install",
            "remove",
            "rename",
            "update",
            "env_create",
            "env_update",
            "list",
        },
    )