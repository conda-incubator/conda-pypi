"""
Tests for authentication functionality.
"""

from unittest.mock import patch, MagicMock
from pathlib import Path

from conda_pypi.auth import (
    get_auth_token_for_url,
    create_authenticated_session,
    is_private_index,
    get_authenticated_index_urls,
    check_anaconda_auth_available,
    get_auth_install_message,
)


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
        assert "token:test-token@" in result[0]


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
        assert "token:test-token@" in result[1]  # authenticated


def test_create_authenticated_session_with_tokens():
    """Test creating authenticated session with tokens."""
    with patch("conda_pypi.auth.get_auth_token_for_url") as mock_get_token:
        mock_get_token.return_value = "test-token"

        session = create_authenticated_session(["https://conda.anaconda.org/test"])

        assert session is not None
        assert hasattr(session, "auth")


def test_create_authenticated_session_no_tokens():
    """Test creating authenticated session without tokens."""
    with patch("conda_pypi.auth.get_auth_token_for_url") as mock_get_token:
        mock_get_token.return_value = None

        session = create_authenticated_session(["https://conda.anaconda.org/test"])

        assert session is not None


def test_get_package_finder_with_authentication():
    """Test that get_package_finder uses authentication when available."""
    from conda_pypi.utils import get_package_finder

    with patch("conda_pypi.auth.create_authenticated_session") as mock_create_session, patch(
        "conda_pypi.auth.get_authenticated_index_urls"
    ) as mock_get_urls:
        mock_session = MagicMock()
        mock_create_session.return_value = mock_session
        mock_get_urls.return_value = ["https://conda.anaconda.org/test"]

        # Create a temporary prefix for testing
        with patch("conda_pypi.utils.get_python_version_for_prefix") as mock_get_version:
            mock_get_version.return_value = "3.9.0"

            finder = get_package_finder(Path("/tmp/test"), ["https://conda.anaconda.org/test"])

            assert finder is not None
            mock_create_session.assert_called_once()
            mock_get_urls.assert_called_once()


def test_get_package_finder_without_authentication():
    """Test that get_package_finder works without authentication."""
    from conda_pypi.utils import get_package_finder

    with patch("conda_pypi.auth.create_authenticated_session", side_effect=ImportError):
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
    with patch("builtins.__import__", side_effect=ImportError):
        assert check_anaconda_auth_available() is False


def test_check_anaconda_auth_available_real_import():
    """Test checking availability with real import."""
    # This test will pass if anaconda-auth is available, fail gracefully if not
    result = check_anaconda_auth_available()
    assert isinstance(result, bool)


def test_get_auth_install_message():
    """Test getting installation message for anaconda-auth."""
    message = get_auth_install_message()
    assert isinstance(message, str)
    assert "anaconda-auth" in message
    assert "pip install conda-pypi[auth]" in message
    assert "conda install anaconda-auth" in message
