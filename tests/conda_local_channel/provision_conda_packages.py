"""
Provision conda packages (Python and dependencies) for local test channel.

Downloads Python 3.12 and all dependencies from conda-forge for specified platforms.
"""

import json
import hashlib
import subprocess
import sys
from pathlib import Path
from urllib import request
from urllib.error import HTTPError, URLError

HERE = Path(__file__).parent
PLATFORMS = ["osx-arm64", "linux-64"]
PYTHON_VERSION = "3.12"
CHANNEL = "conda-forge"


def checksum(path: Path, algorithm: str = "sha256") -> str:
    """Calculate checksum of a file."""
    hasher = hashlib.new(algorithm)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def resolve_dependencies(platform: str) -> list[dict]:
    """
    Use micromamba to resolve Python dependencies for a platform.

    Returns list of package metadata dicts with keys:
    - name, version, build, fn, url, md5, sha256, size, subdir, depends
    """
    cmd = [
        "python",
        "-m",
        "conda",
        "create",
        "-n",
        "temp_resolve",
        f"python={PYTHON_VERSION}",
        "--dry-run",
        "--json",
        "--override-channels",
        "-c",
        CHANNEL,
        "--platform",
        platform,
    ]

    print(f"Resolving dependencies for {platform}...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error resolving dependencies: {result.stderr}")
        sys.exit(1)

    data = json.loads(result.stdout)
    packages = data.get("actions", {}).get("FETCH", [])

    print(f"  Found {len(packages)} packages")
    return packages


def download_package(pkg: dict, dest_dir: Path) -> bool:
    """
    Download a conda package and verify checksum.

    Args:
        pkg: Package metadata dict with url, fn, sha256
        dest_dir: Destination directory (e.g., osx-arm64/)

    Returns:
        True if successful, False otherwise
    """
    url = pkg["url"]
    filename = pkg["fn"]
    expected_sha256 = pkg["sha256"]
    dest_path = dest_dir / filename

    # Check if already exists with correct checksum
    if dest_path.exists():
        actual_sha = checksum(dest_path)
        if actual_sha == expected_sha256:
            print(f"  ✓ {filename} (already exists)")
            return True
        else:
            print(f"  ✗ {filename} has incorrect checksum, re-downloading")
            dest_path.unlink()

    # Download package
    print(f"  Downloading {filename} ({pkg['size'] // 1024} KB)...")
    try:
        request.urlretrieve(url, dest_path)
    except (HTTPError, URLError) as e:
        print(f"    Error: {e}")
        return False

    # Verify checksum
    actual_sha = checksum(dest_path)
    if actual_sha != expected_sha256:
        print(f"  ✗ Checksum mismatch for {filename}")
        dest_path.unlink()
        return False

    print(f"  ✓ {filename}")
    return True


def create_repodata(packages: list[dict], subdir: str) -> dict:
    """
    Create repodata.json structure from package list.

    Note: This creates a minimal repodata.json. For production use,
    run conda-index to generate the full repodata with all metadata.
    """
    repodata = {
        "info": {"subdir": subdir},
        "packages": {},
        "packages.conda": {},
        "removed": [],
        "repodata_version": 1,
    }

    for pkg in packages:
        filename = pkg["fn"]

        # Determine package type
        if filename.endswith(".conda"):
            pkg_dict = "packages.conda"
        elif filename.endswith(".tar.bz2"):
            pkg_dict = "packages"
        else:
            continue

        # Add package metadata
        repodata[pkg_dict][filename] = {
            "build": pkg["build"],
            "build_number": pkg["build_number"],
            "depends": pkg["depends"],
            "license": pkg.get("license", ""),
            "md5": pkg["md5"],
            "name": pkg["name"],
            "sha256": pkg["sha256"],
            "size": pkg["size"],
            "subdir": pkg["subdir"],
            "timestamp": pkg.get("timestamp", 0),
            "version": pkg["version"],
        }

    return repodata


def main():
    print(f"Provisioning Python {PYTHON_VERSION} from {CHANNEL}\n")

    all_successful = True

    for platform in PLATFORMS:
        print(f"\n{'=' * 60}")
        print(f"Platform: {platform}")
        print(f"{'=' * 60}\n")

        # Create platform directory
        platform_dir = HERE / platform
        platform_dir.mkdir(exist_ok=True)

        # Resolve dependencies
        packages = resolve_dependencies(platform)

        # Download packages
        print(f"\nDownloading {len(packages)} packages...\n")
        failed = []
        for pkg in packages:
            if not download_package(pkg, platform_dir):
                failed.append(pkg["fn"])
                all_successful = False

        if failed:
            print(f"\n✗ Failed to download {len(failed)} packages:")
            for fn in failed:
                print(f"  - {fn}")
        else:
            print(f"\n✓ All {len(packages)} packages downloaded successfully")

        # Create minimal repodata.json
        print(f"\nCreating repodata.json for {platform}...")
        repodata = create_repodata(packages, platform)
        repodata_path = platform_dir / "repodata.json"
        repodata_path.write_text(json.dumps(repodata, indent=2))
        print(f"  ✓ {repodata_path}")

    # Final summary
    print(f"\n{'=' * 60}")
    print("Summary")
    print(f"{'=' * 60}\n")

    for platform in PLATFORMS:
        platform_dir = HERE / platform
        packages = list(platform_dir.glob("*.conda")) + list(platform_dir.glob("*.tar.bz2"))
        print(f"{platform}: {len(packages)} packages")

    if all_successful:
        print("\n✓ All platforms provisioned successfully!")
        print("\nNext steps:")
        print("  1. Run generate_index.py to create optimized indexes (optional)")
        print("  2. Run provision_wheels.py if you haven't already")
        print("  3. The conda_local_channel fixture is ready for testing")
    else:
        print("\n✗ Some packages failed to download")
        sys.exit(1)


if __name__ == "__main__":
    main()
