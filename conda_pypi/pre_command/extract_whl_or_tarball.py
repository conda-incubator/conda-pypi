from conda.gateways.disk.create import extract_tarball
from . import extract_whl

def extract_whl_or_tarball(
    source_full_path,
    target_full_path=None,
    progress_update_callback=None,
):
    print("Running extract_whl_tarball", source_full_path)
    if source_full_path.endswith(".whl"):

        return extract_whl.extract_whl_as_conda_pkg(
            source_full_path,
            target_full_path,
        )
    else:
        return extract_tarball(
            source_full_path, target_full_path, progress_update_callback=progress_update_callback
        )
