from __future__ import annotations

import logging
from typing import Optional
from urllib.parse import urlparse


try:
    import anaconda_auth.token

    ANACONDA_AUTH_AVAILABLE = True
except ImportError:
    ANACONDA_AUTH_AVAILABLE = False

logger = logging.getLogger(__name__)


def get_auth_token_for_url(url: str) -> Optional[str]:
    if not ANACONDA_AUTH_AVAILABLE:
        logger.debug("anaconda-auth not available for authentication")
        return None

    try:
        parsed = urlparse(url)
        domain = parsed.netloc

        keyring = anaconda_auth.token.AnacondaKeyring()
        token = keyring.get_password("anaconda-auth", domain)
        if token:
            logger.debug(f"Found token from keyring for {domain}")
            return token

        logger.debug(f"No token found in keyring for {domain}")
        return None
    except Exception as e:
        logger.warning(f"Failed to get authentication token for {url}: {e}")
        return None


def log_authentication_status(index_urls: list[str]) -> None:
    """Log authentication status for private indexes."""
    tokens_found = 0
    for url in index_urls:
        if is_private_index(url):
            token = get_auth_token_for_url(url)
            if token:
                tokens_found += 1
                logger.debug(f"Found token for {urlparse(url).netloc}")

    if tokens_found > 0:
        logger.info(f"Found authentication tokens for {tokens_found} private indexes")


def is_private_index(url: str) -> bool:
    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    return domain not in ["pypi.org", "files.pythonhosted.org"]


def get_authenticated_index_urls(index_urls: list[str]) -> list[str]:
    """Return URLs with embedded tokens for private indexes."""
    authenticated_urls = []

    for url in index_urls:
        if is_private_index(url):
            token = get_auth_token_for_url(url)
            if token:
                parsed = urlparse(url)
                auth_url = f"{parsed.scheme}://user:{token}@{parsed.netloc}{parsed.path}"
                authenticated_urls.append(auth_url)
                logger.debug(f"Embedded token in URL for {parsed.netloc}")
            else:
                authenticated_urls.append(url)
                logger.warning(f"No token found for private index {url}")
        else:
            authenticated_urls.append(url)

    return authenticated_urls


def get_auth_install_message() -> str:
    return (
        "Authentication support requires anaconda-auth. "
        "Install with: pip install conda-pypi[auth] or conda install anaconda-auth"
    )
