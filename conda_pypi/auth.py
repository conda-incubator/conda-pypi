from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse

from pip._internal.network.session import PipSession


def get_auth_token_for_url(url: str) -> Optional[str]:
    try:
        import anaconda_auth

        parsed = urlparse(url)
        domain = parsed.netloc
        token = anaconda_auth.get_token(domain)
        return token
    except ImportError:
        return None
    except Exception:
        return None


def create_authenticated_session(index_urls: list[str]) -> PipSession:
    session = PipSession()

    for url in index_urls:
        token = get_auth_token_for_url(url)
        if token:
            session.auth = (token, "")
            session.headers.update({"Authorization": f"Bearer {token}"})

    return session


def is_private_index(url: str) -> bool:
    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    return domain not in ["pypi.org", "files.pythonhosted.org"]


def get_authenticated_index_urls(index_urls: list[str]) -> list[str]:
    authenticated_urls = []

    for url in index_urls:
        if is_private_index(url):
            token = get_auth_token_for_url(url)
            if token:
                parsed = urlparse(url)
                auth_url = f"{parsed.scheme}://token:{token}@{parsed.netloc}{parsed.path}"
                authenticated_urls.append(auth_url)
            else:
                authenticated_urls.append(url)
        else:
            authenticated_urls.append(url)

    return authenticated_urls


def check_anaconda_auth_available() -> bool:
    try:
        import anaconda_auth  # noqa: F401

        return True
    except ImportError:
        return False
    except Exception:
        return False


def get_auth_install_message() -> str:
    return (
        "Authentication support requires anaconda-auth. "
        "Install with: pip install conda-pypi[auth] or conda install anaconda-auth"
    )
