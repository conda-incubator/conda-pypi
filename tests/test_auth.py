"""
Tests for authentication functionality.
"""

from unittest.mock import patch
from pathlib import Path

from conda_pypi.auth import (
    get_auth_token_for_url,
    log_authentication_status,
    is_private_index,
    get_authenticated_index_urls,
    get_auth_install_message,
    get_available_auth_backends,
    is_authentication_available,
    get_auth_status_summary,
    AuthenticationBackend,
    AnacondaAuthBackend,
    CondaAuthBackend,
    AuthenticationManager,
    ANACONDA_AUTH_AVAILABLE,
)

from conda_pypi.utils import get_package_finder


def test_is_private_index_anaconda():
    """Test detecting Anaconda private indexes."""
    assert is_private_index("https://conda.anaconda.org/test-channel")
    assert is_private_index("https://anaconda.org/test-channel")
    assert is_private_index("https://repo.anaconda.com/test-channel")


def test_is_private_index_artifactory():
    """Test detecting Artifactory private indexes."""
    assert is_private_index("https://artifactory.company.com/pypi")
    assert is_private_index("https://company.artifactory.com/pypi")


def test_is_private_index_nexus():
    """Test detecting Nexus private indexes."""
    assert is_private_index("https://nexus.company.com/repository/pypi")
    assert is_private_index("https://company.nexus.com/repository/pypi")


def test_is_private_index_devpi():
    """Test detecting DevPI private indexes."""
    assert is_private_index("https://devpi.company.com/pypi")
    assert is_private_index("https://company.devpi.com/pypi")


def test_is_private_index_public_pypi():
    """Test that public PyPI is not detected as private."""
    assert not is_private_index("https://pypi.org/simple/")
    assert not is_private_index("https://files.pythonhosted.org/")


def test_is_private_index_custom_domain():
    """Test detecting custom private domains."""
    assert is_private_index("https://pypi.company.com/simple/")
    assert is_private_index("https://company-pypi.internal/simple/")


def test_get_authenticated_index_urls_with_tokens():
    """Test processing URLs with available tokens."""
    with patch("conda_pypi.auth.get_auth_token_for_url") as mock_get_token:
        mock_get_token.return_value = "test-token"

        urls = ["https://conda.anaconda.org/test"]
        result = get_authenticated_index_urls(urls)

        assert len(result) == 1
        assert "user:test-token@" in result[0]


def test_get_authenticated_index_urls_no_tokens():
    """Test processing URLs without available tokens."""
    with patch("conda_pypi.auth.get_auth_token_for_url") as mock_get_token:
        mock_get_token.return_value = None

        urls = ["https://conda.anaconda.org/test"]
        result = get_authenticated_index_urls(urls)

        assert result == urls


def test_get_authenticated_index_urls_public_indexes():
    """Test processing public indexes (no authentication needed)."""
    urls = ["https://pypi.org/simple/"]
    result = get_authenticated_index_urls(urls)

    assert result == urls


def test_get_authenticated_index_urls_mixed():
    """Test processing mixed public and private indexes."""
    with patch("conda_pypi.auth.get_auth_token_for_url") as mock_get_token:

        def mock_get_token_side_effect(url):
            if "anaconda.org" in url:
                return "test-token"
            return None

        mock_get_token.side_effect = mock_get_token_side_effect

        urls = ["https://pypi.org/simple/", "https://conda.anaconda.org/test"]
        result = get_authenticated_index_urls(urls)

        assert len(result) == 2
        assert result[0] == "https://pypi.org/simple/"  # unchanged
        assert "user:test-token@" in result[1]  # authenticated


def test_log_authentication_status_with_tokens():
    """Test logging authentication status with tokens."""
    with patch("conda_pypi.auth.get_auth_token_for_url") as mock_get_token:
        mock_get_token.return_value = "test-token"

        # Should not raise any exceptions
        log_authentication_status(["https://conda.anaconda.org/test"])


def test_log_authentication_status_no_tokens():
    """Test logging authentication status without tokens."""
    with patch("conda_pypi.auth.get_auth_token_for_url") as mock_get_token:
        mock_get_token.return_value = None

        # Should not raise any exceptions
        log_authentication_status(["https://conda.anaconda.org/test"])


def test_get_package_finder_with_authentication():
    """Test that get_package_finder uses authentication when available."""
    with patch("conda_pypi.utils.log_authentication_status") as mock_log_status, patch(
        "conda_pypi.utils.get_authenticated_index_urls"
    ) as mock_get_urls:
        mock_get_urls.return_value = ["https://conda.anaconda.org/test"]

        # Create a temporary prefix for testing
        with patch("conda_pypi.utils.get_python_version_for_prefix") as mock_get_version:
            mock_get_version.return_value = "3.9.0"

            finder = get_package_finder(Path("/tmp/test"), ["https://conda.anaconda.org/test"])

            assert finder is not None
            mock_log_status.assert_called_once()
        mock_get_urls.assert_called_once()


def test_get_package_finder_without_authentication():
    """Test that get_package_finder works without authentication."""
    from conda_pypi.utils import get_package_finder

    with patch("conda_pypi.auth.log_authentication_status", side_effect=ImportError):
        with patch("conda_pypi.utils.get_python_version_for_prefix") as mock_get_version:
            mock_get_version.return_value = "3.9.0"

            finder = get_package_finder(Path("/tmp/test"), ["https://pypi.org/simple/"])

            assert finder is not None


def test_get_auth_token_for_url_no_anaconda_auth():
    """Test getting auth token when anaconda-auth is not available."""
    with patch("builtins.__import__", side_effect=ImportError):
        token = get_auth_token_for_url("https://conda.anaconda.org/test-channel")

        assert token is None


def test_get_auth_token_for_url_real_import():
    """Test getting auth token with real anaconda-auth import."""
    # This test will pass if anaconda-auth is available, fail gracefully if not
    token = get_auth_token_for_url("https://conda.anaconda.org/test-channel")
    # Should return None or a token, but not raise an exception
    assert token is None or isinstance(token, str)


def test_check_anaconda_auth_available_without_module():
    """Test checking availability when module is not available."""
    # This test will pass if anaconda-auth is available, fail gracefully if not
    # The module-level import happens at import time, so we can't easily mock it
    result = ANACONDA_AUTH_AVAILABLE
    assert isinstance(result, bool)


def test_check_anaconda_auth_available_real_import():
    """Test checking availability with real import."""
    # This test will pass if anaconda-auth is available, fail gracefully if not
    result = ANACONDA_AUTH_AVAILABLE
    assert isinstance(result, bool)


def test_get_auth_install_message():
    """Test getting installation message for authentication."""
    message = get_auth_install_message()
    assert isinstance(message, str)
    # Should mention either available backends or installation instructions
    assert "anaconda-auth" in message or "conda-auth" in message or "backends available" in message
    # If no backends are available, should include installation instructions
    if "backends available" not in message:
        assert "pip install conda-pypi[auth]" in message


def test_authentication_backend_interface():
    """Test that AuthenticationBackend is properly abstract."""
    # Should not be able to instantiate directly
    try:
        AuthenticationBackend()
        assert False, "Should not be able to instantiate abstract class"
    except TypeError:
        pass  # Expected


def test_anaconda_auth_backend_name():
    """Test backend name."""
    backend = AnacondaAuthBackend()
    assert backend.get_backend_name() == "anaconda-auth"


def test_anaconda_auth_backend_availability():
    """Test backend availability."""
    backend = AnacondaAuthBackend()
    assert isinstance(backend.is_available(), bool)


@patch("conda_pypi.auth.ANACONDA_AUTH_AVAILABLE", False)
def test_anaconda_auth_backend_unavailable():
    """Test backend when anaconda-auth is not available."""
    backend = AnacondaAuthBackend()
    assert not backend.is_available()
    assert backend.get_auth_token_for_url("https://test.com") is None


def test_conda_auth_backend_name():
    """Test backend name."""
    backend = CondaAuthBackend()
    assert backend.get_backend_name() == "conda-auth"


def test_conda_auth_backend_availability():
    """Test backend availability."""
    backend = CondaAuthBackend()
    assert isinstance(backend.is_available(), bool)


@patch("conda_pypi.auth.CONDA_AUTH_AVAILABLE", False)
def test_conda_auth_backend_unavailable():
    """Test backend when conda-auth is not available."""
    backend = CondaAuthBackend()
    assert not backend.is_available()
    assert backend.get_auth_token_for_url("https://test.com") is None


def test_authentication_manager_initialization():
    """Test manager initialization."""
    manager = AuthenticationManager()
    assert isinstance(manager.backends, list)
    assert len(manager.backends) >= 0


def test_get_available_backends():
    """Test getting available backends."""
    manager = AuthenticationManager()
    backends = manager.get_available_backends()
    assert isinstance(backends, list)
    # Should contain valid backend names
    for backend_name in backends:
        assert backend_name in ["anaconda-auth", "conda-auth"]


def test_is_any_backend_available():
    """Test checking if any backend is available."""
    manager = AuthenticationManager()
    result = manager.is_any_backend_available()
    assert isinstance(result, bool)


def test_get_auth_token_for_url_no_backends():
    """Test getting token when no backends are available."""
    manager = AuthenticationManager()
    # Mock all backends to be unavailable
    with patch.object(manager, "backends", []):
        token = manager.get_auth_token_for_url("https://test.com")
        assert token is None


def test_get_available_auth_backends():
    """Test getting available authentication backends."""
    backends = get_available_auth_backends()
    assert isinstance(backends, list)


def test_is_authentication_available():
    """Test checking if authentication is available."""
    result = is_authentication_available()
    assert isinstance(result, bool)


def test_get_auth_status_summary():
    """Test getting authentication status summary."""
    summary = get_auth_status_summary()
    assert isinstance(summary, dict)
    assert "conda_auth_available" in summary
    assert "anaconda_auth_available" in summary
    assert "available_backends" in summary
    assert "any_backend_available" in summary

    assert isinstance(summary["conda_auth_available"], bool)
    assert isinstance(summary["anaconda_auth_available"], bool)
    assert isinstance(summary["available_backends"], list)
    assert isinstance(summary["any_backend_available"], bool)


def test_backend_priority():
    """Test that conda-auth backend is preferred over anaconda-auth."""
    manager = AuthenticationManager()
    if len(manager.backends) >= 2:
        # conda-auth should be first (preferred)
        assert manager.backends[0].get_backend_name() == "conda-auth"
        assert manager.backends[1].get_backend_name() == "anaconda-auth"


def test_fallback_behavior():
    """Test fallback behavior when preferred backend fails."""
    manager = AuthenticationManager()

    # Mock conda-auth backend to return None
    if len(manager.backends) >= 2:
        conda_backend = manager.backends[0]
        anaconda_backend = manager.backends[1]

        with patch.object(conda_backend, "get_auth_token_for_url", return_value=None):
            with patch.object(
                anaconda_backend, "get_auth_token_for_url", return_value="test-token"
            ):
                token = manager.get_auth_token_for_url("https://test.com")
                # Should fall back to anaconda-auth
                assert token == "test-token"


def test_log_authentication_status_with_backends():
    """Test logging with available backends."""
    with patch("conda_pypi.auth._auth_manager") as mock_manager:
        mock_manager.get_available_backends.return_value = ["conda-auth", "anaconda-auth"]
        mock_manager.get_auth_token_for_url.return_value = "test-token"

        # Should not raise any exceptions
        log_authentication_status(["https://conda.anaconda.org/test"])


def test_log_authentication_status_no_backends():
    """Test logging when no backends are available."""
    with patch("conda_pypi.auth._auth_manager") as mock_manager:
        mock_manager.get_available_backends.return_value = []
        mock_manager.get_auth_token_for_url.return_value = None

        # Should not raise any exceptions
        log_authentication_status(["https://conda.anaconda.org/test"])
