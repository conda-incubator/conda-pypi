from __future__ import annotations

import logging
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse
from abc import ABC, abstractmethod

try:
    import keyring
except ImportError:
    keyring = None

try:
    from conda.models.channel import Channel
except ImportError:
    Channel = None


try:
    import anaconda_auth.token

    ANACONDA_AUTH_AVAILABLE = True
except ImportError:
    ANACONDA_AUTH_AVAILABLE = False

try:
    import conda_auth  # noqa: F401

    CONDA_AUTH_AVAILABLE = True
except ImportError:
    CONDA_AUTH_AVAILABLE = False

logger = logging.getLogger(__name__)


class AuthenticationBackend(ABC):
    """Abstract base class for authentication backends."""

    @abstractmethod
    def get_auth_token_for_url(self, url: str) -> Optional[str]:
        """Get authentication token for a given URL."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this authentication backend is available."""
        pass

    @abstractmethod
    def get_backend_name(self) -> str:
        """Get the name of this authentication backend."""
        pass


class AnacondaAuthBackend(AuthenticationBackend):
    """anaconda-auth backend for Anaconda systems."""

    def get_auth_token_for_url(self, url: str) -> Optional[str]:
        if not self.is_available():
            logger.debug("anaconda-auth not available for authentication")
            return None

        try:
            parsed = urlparse(url)
            domain = parsed.netloc

            keyring = anaconda_auth.token.AnacondaKeyring()
            token = keyring.get_password("anaconda-auth", domain)
            if token:
                logger.debug(f"Found anaconda-auth token from keyring for {domain}")
                return token

            logger.debug(f"No anaconda-auth token found in keyring for {domain}")
            return None
        except Exception as e:
            logger.warning(f"Failed to get anaconda-auth token for {url}: {e}")
            return None

    def is_available(self) -> bool:
        return ANACONDA_AUTH_AVAILABLE

    def get_backend_name(self) -> str:
        return "anaconda-auth"


class CondaAuthBackend(AuthenticationBackend):
    """conda-auth backend supporting multiple authentication systems."""

    def get_auth_token_for_url(self, url: str) -> Optional[str]:
        if not self.is_available():
            logger.debug("conda-auth not available for authentication")
            return None

        try:
            parsed = urlparse(url)
            domain = parsed.netloc

            auth_info = self._get_auth_for_domain(domain)
            if auth_info:
                logger.debug(f"Found conda-auth token for {domain}")
                return auth_info.get("token")

            logger.debug(f"No conda-auth token found for {domain}")
            return None
        except Exception as e:
            logger.warning(f"Failed to get conda-auth token for {url}: {e}")
            return None

    def _get_auth_for_domain(self, domain: str) -> Optional[Dict[str, Any]]:
        """Get authentication information for a domain using conda-auth."""
        if not keyring or not Channel:
            logger.debug("keyring or Channel not available for conda-auth")
            return None

        try:
            # Try different channel name formats
            channel_names = [
                domain,
                f"https://{domain}",
                f"https://{domain}/",
                f"https://{domain}/simple/",
            ]

            for channel_name in channel_names:
                try:
                    channel = Channel(channel_name)
                    keyring_id = f"conda-auth::token::{channel.canonical_name}"
                    token = keyring.get_password(keyring_id, "token")
                    if token:
                        logger.debug(
                            f"Found conda-auth token for {domain} using channel {channel_name}"
                        )
                        return {"token": token}
                except Exception:
                    continue

            logger.debug(f"No conda-auth credentials found for {domain}")
        except Exception as e:
            logger.debug(f"Failed to get conda-auth credentials for {domain}: {e}")
        return None

    def is_available(self) -> bool:
        return CONDA_AUTH_AVAILABLE

    def get_backend_name(self) -> str:
        return "conda-auth"


class AuthenticationManager:
    """Manages multiple authentication backends."""

    def __init__(self):
        self.backends: List[AuthenticationBackend] = []
        self._initialize_backends()

    def _initialize_backends(self):
        """Initialize available authentication backends."""
        if CONDA_AUTH_AVAILABLE:
            self.backends.append(CondaAuthBackend())
            logger.debug("Initialized conda-auth backend")

        if ANACONDA_AUTH_AVAILABLE:
            self.backends.append(AnacondaAuthBackend())
            logger.debug("Initialized anaconda-auth backend")

        if not self.backends:
            logger.debug("No authentication backends available")

    def get_auth_token_for_url(self, url: str) -> Optional[str]:
        """Get authentication token from the first available backend."""
        for backend in self.backends:
            if backend.is_available():
                token = backend.get_auth_token_for_url(url)
                if token:
                    logger.debug(f"Found token using {backend.get_backend_name()} backend")
                    return token

        logger.debug("No authentication token found for any backend")
        return None

    def get_available_backends(self) -> List[str]:
        """Get list of available authentication backends."""
        return [backend.get_backend_name() for backend in self.backends if backend.is_available()]

    def is_any_backend_available(self) -> bool:
        """Check if any authentication backend is available."""
        return any(backend.is_available() for backend in self.backends)


# Global authentication manager instance
_auth_manager = AuthenticationManager()


def get_auth_token_for_url(url: str) -> Optional[str]:
    """Get authentication token for a URL using available backends."""
    return _auth_manager.get_auth_token_for_url(url)


def log_authentication_status(index_urls: list[str]) -> None:
    """Log authentication status for private indexes."""
    tokens_found = 0
    available_backends = _auth_manager.get_available_backends()

    if available_backends:
        logger.debug(f"Available authentication backends: {', '.join(available_backends)}")

    for url in index_urls:
        if is_private_index(url):
            token = get_auth_token_for_url(url)
            if token:
                tokens_found += 1
                logger.debug(f"Found token for {urlparse(url).netloc}")

    if tokens_found > 0:
        logger.info(f"Found authentication tokens for {tokens_found} private indexes")
    elif any(is_private_index(url) for url in index_urls):
        logger.warning("Private indexes detected but no authentication tokens found")
        logger.info("Consider running: conda auth login or anaconda login")


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
    """Get installation message for authentication support."""
    available_backends = _auth_manager.get_available_backends()

    if available_backends:
        return f"Authentication backends available: {', '.join(available_backends)}"

    return (
        "Authentication support requires conda-auth or anaconda-auth. "
        "Install with: pip install conda-pypi[auth] or conda install conda-auth anaconda-auth"
    )


def get_available_auth_backends() -> List[str]:
    """Get list of available authentication backends."""
    return _auth_manager.get_available_backends()


def is_authentication_available() -> bool:
    """Check if any authentication backend is available."""
    return _auth_manager.is_any_backend_available()


def get_auth_status_summary() -> Dict[str, Any]:
    """Get comprehensive authentication status summary."""
    return {
        "conda_auth_available": CONDA_AUTH_AVAILABLE,
        "anaconda_auth_available": ANACONDA_AUTH_AVAILABLE,
        "available_backends": _auth_manager.get_available_backends(),
        "any_backend_available": _auth_manager.is_any_backend_available(),
    }
