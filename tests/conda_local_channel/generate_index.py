"""
Generate conda channel index files using conda-index.

This creates repodata.json.zst and channeldata.json for all subdirectories.
"""

from pathlib import Path
from conda_pypi.index import update_index

HERE = Path(__file__).parent

if __name__ == "__main__":
    print("Generating conda channel indexes...")
    print(f"Channel directory: {HERE}\n")

    try:
        # Update index for the entire channel (handles all subdirs)
        update_index(HERE)

        print("\n✓ Indexes generated successfully")

        # List generated files
        for subdir in ["noarch", "osx-arm64", "linux-64"]:
            subdir_path = HERE / subdir
            if subdir_path.exists():
                print(f"\n{subdir}/:")
                if (subdir_path / "repodata.json").exists():
                    print("  - repodata.json")
                if (subdir_path / "repodata.json.zst").exists():
                    print("  - repodata.json.zst")

        if (HERE / "channeldata.json").exists():
            print("\nRoot:")
            print("  - channeldata.json")

    except Exception as e:
        print(f"\n✗ Error generating indexes: {e}")
        print("This is optional - the fixture will work without compressed indexes")
