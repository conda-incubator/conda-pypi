"""
Provision wheel files for the conda local channel test fixture.

This script downloads the wheel files referenced in repodata.json
from PyPI and verifies their checksums.
"""

import hashlib
import json
import sys
from pathlib import Path
from urllib import request
from urllib.error import HTTPError, URLError


HERE = Path(__file__).parent
NOARCH = HERE / "noarch"
REPODATA = NOARCH / "repodata.json"


def checksum(path: Path, algorithm: str = "sha256") -> str:
    """Calculate checksum of a file."""
    hasher = hashlib.new(algorithm)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def download_wheel(url: str, dest: Path, expected_sha256: str) -> bool:
    """
    Download wheel and verify checksum.

    Returns True if download was successful, False otherwise.
    """
    if dest.exists():
        # Verify existing file
        actual_sha = checksum(dest)
        if actual_sha == expected_sha256:
            print(f"✓ {dest.name} already exists with correct checksum")
            return True
        else:
            print(f"✗ {dest.name} has incorrect checksum, re-downloading")
            dest.unlink()

    print(f"Downloading {dest.name}...")
    try:
        request.urlretrieve(url, dest)
    except (HTTPError, URLError) as e:
        print(f"  Error downloading: {e}")
        return False

    # Verify checksum
    actual_sha = checksum(dest)
    if actual_sha != expected_sha256:
        print(f"✗ Checksum mismatch for {dest.name}")
        print(f"  Expected: {expected_sha256}")
        print(f"  Got:      {actual_sha}")
        dest.unlink()
        return False

    print(f"✓ {dest.name} downloaded successfully")
    return True


def construct_pypi_url(package_name: str, filename: str) -> list[str]:
    """
    Construct possible PyPI URLs for a wheel file.

    PyPI uses multiple URL patterns. Returns a list of URLs to try.
    """
    # Normalize package name for PyPI (replace underscores with hyphens)
    normalized_name = package_name.replace("_", "-")

    # Try multiple URL patterns
    urls = []

    # Pattern 1: Simple index format with first letter
    first_letter = normalized_name[0].lower()
    urls.append(
        f"https://files.pythonhosted.org/packages/py3/{first_letter}/{normalized_name}/{filename}"
    )

    # Pattern 2: Try with original package name
    if normalized_name != package_name:
        first_letter = package_name[0].lower()
        urls.append(
            f"https://files.pythonhosted.org/packages/py3/{first_letter}/{package_name}/{filename}"
        )

    # Pattern 3: Use PyPI JSON API to get the correct URL
    urls.append(f"https://pypi.org/pypi/{normalized_name}/json")

    return urls


def download_from_pypi_api(package_name: str, filename: str, dest: Path) -> str | None:
    """
    Use PyPI JSON API to find the correct download URL.

    Returns the download URL if found, None otherwise.
    """
    normalized_name = package_name.replace("_", "-")
    api_url = f"https://pypi.org/pypi/{normalized_name}/json"

    try:
        with request.urlopen(api_url) as response:
            data = json.loads(response.read())

            # Search through all releases for the matching filename
            for version, files in data.get("releases", {}).items():
                for file_info in files:
                    if file_info["filename"] == filename:
                        return file_info["url"]
    except (HTTPError, URLError, KeyError, json.JSONDecodeError):
        pass

    return None


def main():
    if not REPODATA.exists():
        print(f"Error: {REPODATA} not found")
        sys.exit(1)

    repodata = json.loads(REPODATA.read_text())

    if "packages.whl" not in repodata:
        print("No packages.whl section found in repodata.json")
        return

    total = len(repodata["packages.whl"])
    successful = 0
    failed = []

    print(f"Found {total} wheel files to provision\n")

    for filename, metadata in repodata["packages.whl"].items():
        wheel_path = NOARCH / filename
        package_name = metadata["name"]
        sha256_hash = metadata["sha256"]

        print(f"Processing {filename}...")

        # Try direct URLs first
        urls = construct_pypi_url(package_name, filename)
        success = False

        for url in urls[:2]:  # Try the first two direct URL patterns
            if download_wheel(url, wheel_path, sha256_hash):
                successful += 1
                success = True
                break

        if not success:
            # Try PyPI API as fallback
            print("  Trying PyPI API...")
            api_url = download_from_pypi_api(package_name, filename, wheel_path)

            if api_url:
                print(f"  Found URL: {api_url}")
                if download_wheel(api_url, wheel_path, sha256_hash):
                    successful += 1
                    success = True

        if not success:
            failed.append((filename, package_name))
            print(f"✗ Failed to download {filename}\n")
        else:
            print()

    print(f"\n{'=' * 60}")
    print(f"Summary: {successful}/{total} wheels downloaded successfully")

    if failed:
        print(f"\nFailed downloads ({len(failed)}):")
        for filename, package_name in failed:
            print(f"  - {filename} (package: {package_name})")
            print("    You may need to manually download this wheel from:")
            print(f"    https://pypi.org/project/{package_name}/#files")
        sys.exit(1)
    else:
        print("\n✓ All wheels provisioned successfully!")


if __name__ == "__main__":
    main()
