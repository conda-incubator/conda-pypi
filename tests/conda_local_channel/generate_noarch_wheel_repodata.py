import requests
import json
from datetime import datetime
from typing import Dict, Any, Optional


repodata_packages = [
    ('requests', '2.32.5'), ('anyio', '4.9.0'), 
    ('setuptools', '78.1.1'), ('starlette', '0.47.2'), 
    ('typing_extensions', '4.14.1'), 
    ('wheel', '0.45.1'), ('sniffio', '1.3.1'), 
    ('typing-inspection', '0.4.1'), ('annotated-types', '0.7.0'), 
    ('fastapi', '0.116.1'), ('idna', '3.10'), 
    ('charset_normalizer', '3.3.2'), ('urllib3', '2.2.3'),
    ('certifi', '2024.12.14'), ('auto-all', '1.4.1'), 
    ('fire', '0.7.1'), ('typeguard', '4.4.1'), 
    ('exceptiongroup', '1.2.2'), ('termcolor', '2.5.0'),
]

def pypi_to_repodata_whl_entry(pypi_data: Dict[str, Any], url_index: int = 0) -> Optional[Dict[str, Any]]:
    """
    Convert PyPI JSON endpoint data to a repodata.json packages.whl entry.
    
    Args:
        pypi_info: Dictionary containing the complete info section from PyPI JSON endpoint
        url_index: Index of the wheel URL to use (typically the first one is the wheel)
    
    Returns:
        Dictionary representing the entry for packages.whl, or None if wheel not found
    """
    # Find the wheel URL (bdist_wheel package type)
    wheel_url = None
    
    # import pdb; pdb.set_trace()
    for url_entry in pypi_data.get("urls", []):
        if url_entry.get("packagetype") == "bdist_wheel":
            wheel_url = url_entry
            break
    
    if not wheel_url:
        return None
    
    pypi_info = pypi_data.get("info")

    depends_list = []
    for dep in pypi_info.get("requires_dist") or []:
        if "extra" not in dep:
            depends_list.append(dep.split(";")[0])
    depends_list.append(f"python { pypi_info.get('requires_python')}")
    
    # Build the repodata entry
    entry = {
        "url": wheel_url.get("url", ""),
        "record_version": 3,
        "name": pypi_info.get('name'),
        "version": pypi_info.get('version'),
        "build": "py3_none_any_0",
        "build_number": 0,
        "depends": depends_list,
        "fn": f"{pypi_info.get('name')}-{pypi_info.get('version')}-py3-none-any.whl",
        "sha256": wheel_url.get("digests", {}).get("sha256", ""),
        "size": wheel_url.get("size", 0),
        "subdir": "noarch",
        # "timestamp": wheel_url.get("upload_time", 0),
        "noarch": "python",
    }
    
    return entry


def get_repodata_entry(name: str, version: str):
    pypi_endpoint = f"https://pypi.org/pypi/{name}/{version}/json"
    pypi_data = requests.get(pypi_endpoint)
    if pypi_data.json() is None:
        raise Exception(f"unable to process {name} {version}")
    return pypi_to_repodata_whl_entry(pypi_data.json())
    

if __name__ == "__main__":
    from pathlib import Path

    HERE = Path(__file__).parent
    wheel_repodata = HERE / "noarch/repodata.json"
    
    pkg_whls = {}

    for pkg_tuple in repodata_packages:
        name = pkg_tuple[0]
        version = pkg_tuple[1]
        pkg_whls[f"{name}-{version}-py3_none_any_0"] = get_repodata_entry(name, version)
    
    repodata_output = {
        "info": {
            "subdir": "noarch"
        },
        "packages": {},
        "packages.conda": {},
        "removed": [],
        "repodata_version": 1,
        "signatures": {},
        "packages.whl": pkg_whls,
    }

    with open(wheel_repodata, "w") as f:
        json.dump(repodata_output, f, indent=4)