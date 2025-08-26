"""
Interface to conda-index.
"""

from conda_index.index import ChannelIndex


def update_index(path):
    channel_index = ChannelIndex(
        path,
        None,
        threads=1,
        debug=False,
        write_bz2=False,
        write_zst=True,
        write_run_exports=True,
        compact_json=True,
        write_current_repodata=False,
    )
    channel_index.index(patch_generator=None)
    channel_index.update_channeldata()
