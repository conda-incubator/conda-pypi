"""VCS repository handling for conda-pypi."""

import subprocess
from pathlib import Path
from typing import NamedTuple, Optional
import logging

log = logging.getLogger(__name__)


class VCSInfo(NamedTuple):
    scheme: str
    url: str
    ref: Optional[str] = None
    subdirectory: Optional[str] = None


class VCSHandler:
    SUPPORTED_SCHEMES = ["git+", "hg+", "svn+", "bzr+"]

    @classmethod
    def is_vcs_url(cls, url: str) -> bool:
        return any(url.startswith(scheme) for scheme in cls.SUPPORTED_SCHEMES)

    @classmethod
    def parse_vcs_url(cls, url: str) -> VCSInfo:
        if not cls.is_vcs_url(url):
            raise ValueError(f"Not a VCS URL: {url}")

        # Parse URLs like: git+https://github.com/user/repo.git@branch#egg=package&subdirectory=subdir
        scheme = url.split("+", 1)[0]
        rest = url[len(scheme) + 1 :]

        # Split on # to separate URL from fragment
        if "#" in rest:
            base_url, fragment = rest.split("#", 1)
            # Parse fragment for subdirectory
            if "&subdirectory=" in fragment:
                subdirectory = fragment.split("&subdirectory=")[1].split("&")[0]
            else:
                subdirectory = None
        else:
            base_url = rest
            subdirectory = None

        # Split on @ to separate URL from ref
        if "@" in base_url:
            url_part, ref = base_url.rsplit("@", 1)
        else:
            url_part = base_url
            ref = None

        return VCSInfo(scheme=scheme, url=url_part, ref=ref, subdirectory=subdirectory)

    @classmethod
    def clone_repository(cls, vcs_info: VCSInfo, target_dir: Path) -> Path:
        target_dir.mkdir(parents=True, exist_ok=True)
        repo_path = target_dir / "repo"

        if vcs_info.scheme == "git":
            cmd = ["git", "clone"]
            if vcs_info.ref:
                cmd.extend(["--branch", vcs_info.ref])
            cmd.extend(["--depth", "1", vcs_info.url, str(repo_path)])
        elif vcs_info.scheme == "hg":
            cmd = ["hg", "clone"]
            if vcs_info.ref:
                cmd.extend(["--rev", vcs_info.ref])
            cmd.extend([vcs_info.url, str(repo_path)])
        elif vcs_info.scheme == "svn":
            cmd = ["svn", "checkout", vcs_info.url, str(repo_path)]
            if vcs_info.ref:
                cmd[-2] = f"{vcs_info.url}@{vcs_info.ref}"
        elif vcs_info.scheme == "bzr":
            cmd = ["bzr", "branch"]
            if vcs_info.ref:
                cmd.extend(["--revision", vcs_info.ref])
            cmd.extend([vcs_info.url, str(repo_path)])
        else:
            raise ValueError(f"Unsupported VCS scheme: {vcs_info.scheme}")

        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            log.info(f"Cloned {vcs_info.scheme} repository to {repo_path}")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to clone {vcs_info.url}: {e.stderr}")

        if vcs_info.subdirectory:
            subdir_path = repo_path / vcs_info.subdirectory
            if not subdir_path.exists():
                raise ValueError(f"Subdirectory not found: {vcs_info.subdirectory}")
            return subdir_path

        return repo_path
