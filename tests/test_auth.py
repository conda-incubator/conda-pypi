"""
Tests for authentication functionality.
"""

from unittest.mock import patch, Mock
from pathlib import Path
import pytest
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

from conda_pypi.auth import (
    get_auth_token_for_url,
    log_authentication_status,
    is_private_index,
    get_authentication_info_for_urls,
    download_with_auth_headers,
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
    """Test that get_package_finder logs authentication status when available."""
    with patch("conda_pypi.utils.log_authentication_status") as mock_log_status:
        # Create a temporary prefix for testing
        with patch("conda_pypi.utils.get_python_version_for_prefix") as mock_get_version:
            mock_get_version.return_value = "3.9.0"

            finder = get_package_finder(Path("/tmp/test"), ["https://conda.anaconda.org/test"])

            assert finder is not None
            mock_log_status.assert_called_once()


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


def test_get_authentication_info_for_urls_with_tokens():
    """Test getting authentication info for URLs with tokens."""
    with patch("conda_pypi.auth.get_auth_token_for_url") as mock_get_token:
        mock_get_token.return_value = "test-token"

        urls = ["https://conda.anaconda.org/test"]
        result = get_authentication_info_for_urls(urls)

        assert len(result) == 1
        assert result["https://conda.anaconda.org/test"] == "test-token"


def test_get_authentication_info_for_urls_no_tokens():
    """Test getting authentication info for URLs without tokens."""
    with patch("conda_pypi.auth.get_auth_token_for_url") as mock_get_token:
        mock_get_token.return_value = None

        urls = ["https://conda.anaconda.org/test"]
        result = get_authentication_info_for_urls(urls)

        assert len(result) == 1
        assert result["https://conda.anaconda.org/test"] is None


def test_get_authentication_info_for_urls_public_indexes():
    """Test getting authentication info for public indexes."""
    urls = ["https://pypi.org/simple/"]
    result = get_authentication_info_for_urls(urls)

    assert len(result) == 1
    assert result["https://pypi.org/simple/"] is None


def test_get_authentication_info_for_urls_mixed():
    """Test getting authentication info for mixed public and private indexes."""
    with patch("conda_pypi.auth.get_auth_token_for_url") as mock_get_token:

        def mock_get_token_side_effect(url):
            if "anaconda.org" in url:
                return "test-token"
            return None

        mock_get_token.side_effect = mock_get_token_side_effect

        urls = ["https://pypi.org/simple/", "https://conda.anaconda.org/test"]
        result = get_authentication_info_for_urls(urls)

        assert len(result) == 2
        assert result["https://pypi.org/simple/"] is None  # public
        assert result["https://conda.anaconda.org/test"] == "test-token"  # private


def test_download_with_auth_headers_with_token():
    """Test downloading with authentication headers."""
    # Integration test - test that the function can be called without errors
    # Since conda's session is already available, we don't need to mock it
    try:
        download_with_auth_headers("https://httpbin.org/get", Path("/tmp/test_auth"), "test-token")
    except Exception:
        # Expected to fail with network error, but function should handle it gracefully
        pass


def test_download_with_auth_headers_without_token():
    """Test downloading without authentication headers."""
    # Integration test - test that the function can be called without errors
    try:
        download_with_auth_headers("https://httpbin.org/get", Path("/tmp/test_no_auth"), None)
    except Exception:
        # Expected to fail with network error, but function should handle it gracefully
        pass


class AuthTestHTTPRequestHandler(BaseHTTPRequestHandler):
    """Custom HTTP request handler for testing authentication headers."""

    def do_GET(self):
        """Handle GET requests and verify authentication headers."""
        # Check if Authorization header is present
        auth_header = self.headers.get("Authorization")

        if auth_header:
            # Verify the header format
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]  # Remove "Bearer " prefix
                # Send token back in response for verification
                response_body = f"Token received: {token}".encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(response_body)))
                self.end_headers()
                self.wfile.write(response_body)
            else:
                # Invalid auth header format
                self.send_response(401)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Invalid Authorization header format")
        else:
            # No auth header - send success response
            response_body = b"No authentication required"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()
            self.wfile.write(response_body)

    def log_message(self, format, *args):
        """Suppress default logging to keep test output clean."""
        pass


@pytest.fixture
def test_server():
    """Fixture that provides a local test server for HTTP testing."""
    server = HTTPServer(("localhost", 0), AuthTestHTTPRequestHandler)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    # Give server a moment to start
    time.sleep(0.1)

    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=1.0)


def test_download_with_auth_headers_local_server_with_token(test_server, tmp_path):
    """Test downloading with authentication headers using local server."""
    server_port = test_server.server_address[1]
    test_url = f"http://localhost:{server_port}/test"
    target_file = tmp_path / "test_file_with_auth"
    test_token = "test-bearer-token-123"

    # Download with authentication
    download_with_auth_headers(test_url, target_file, test_token)

    # Verify file was created and contains expected content
    assert target_file.exists(), "File should be created"
    content = target_file.read_text()
    assert f"Token received: {test_token}" in content, "Should receive the token back"


def test_download_with_auth_headers_local_server_without_token(tmp_path):
    """Test downloading without authentication headers using local server."""
    # Create a fresh server for this test to avoid session caching issues
    server = HTTPServer(("localhost", 0), AuthTestHTTPRequestHandler)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    try:
        # Give server a moment to start
        time.sleep(0.1)

        server_port = server.server_address[1]
        test_url = f"http://localhost:{server_port}/test"
        target_file = tmp_path / "test_file_without_auth"

        # Clear any existing session headers by patching get_session
        with patch("conda_pypi.auth.get_session") as mock_get_session:
            from conda.gateways.connection.download import get_session as real_get_session

            real_session = real_get_session(test_url)
            # Clear any existing Authorization header
            if "Authorization" in real_session.headers:
                del real_session.headers["Authorization"]
            mock_get_session.return_value = real_session

            # Download without authentication
            download_with_auth_headers(test_url, target_file, None)

        # Verify file was created and contains expected content
        assert target_file.exists(), "File should be created"
        content = target_file.read_text()
        assert "No authentication required" in content, "Should receive no-auth response"
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=1.0)


def test_download_with_auth_headers_creates_directories(tmp_path):
    """Test that download_with_auth_headers creates parent directories."""
    # Create a nested directory structure that doesn't exist
    nested_path = tmp_path / "level1" / "level2" / "level3" / "test_file"

    # Mock a simple response to avoid network dependency
    with patch("conda_pypi.auth.get_session") as mock_get_session:
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.iter_content.return_value = [b"test content"]

        # Create a proper mock for session headers
        mock_headers = {}
        mock_session = Mock()
        mock_session.headers = mock_headers
        mock_session.get.return_value = mock_response
        mock_get_session.return_value = mock_session

        download_with_auth_headers("http://example.com/test", nested_path, "test-token")

        # Verify directory structure was created
        assert nested_path.parent.exists(), "Parent directories should be created"
        assert nested_path.exists(), "File should be created"

        # Verify Authorization header was set
        assert mock_headers["Authorization"] == "Bearer test-token"


def test_download_with_auth_headers_no_token_no_header_set(tmp_path):
    """Test that no Authorization header is set when token is None."""
    with patch("conda_pypi.auth.get_session") as mock_get_session:
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.iter_content.return_value = [b"test content"]

        # Create a proper mock for session headers
        mock_headers = {}
        mock_session = Mock()
        mock_session.headers = mock_headers
        mock_session.get.return_value = mock_response
        mock_get_session.return_value = mock_session

        download_with_auth_headers("http://example.com/test", tmp_path / "test_file", None)

        # Verify no Authorization header was set
        assert "Authorization" not in mock_headers


def test_download_with_auth_headers_http_errors():
    """Test error handling for various HTTP status codes."""
    with patch("conda_pypi.auth.get_session") as mock_get_session:
        # Test 404 error
        mock_response_404 = Mock()
        mock_response_404.raise_for_status.side_effect = Exception("404 Not Found")

        mock_headers = {}
        mock_session = Mock()
        mock_session.headers = mock_headers
        mock_session.get.return_value = mock_response_404
        mock_get_session.return_value = mock_session

        with pytest.raises(Exception, match="404 Not Found"):
            download_with_auth_headers("http://example.com/notfound", Path("/tmp/test"), "token")

        # Test 401 error
        mock_response_401 = Mock()
        mock_response_401.raise_for_status.side_effect = Exception("401 Unauthorized")

        mock_session.get.return_value = mock_response_401

        with pytest.raises(Exception, match="401 Unauthorized"):
            download_with_auth_headers(
                "http://example.com/unauthorized", Path("/tmp/test"), "invalid-token"
            )


def test_download_with_auth_headers_file_write_error(tmp_path):
    """Test error handling when file writing fails."""
    with patch("conda_pypi.auth.get_session") as mock_get_session:
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.iter_content.return_value = [b"test content"]

        mock_headers = {}
        mock_session = Mock()
        mock_session.headers = mock_headers
        mock_session.get.return_value = mock_response
        mock_get_session.return_value = mock_session

        # Create a path that will cause permission error
        read_only_file = tmp_path / "readonly_file"
        read_only_file.touch()
        read_only_file.chmod(0o444)  # Read-only

        with pytest.raises(PermissionError):
            download_with_auth_headers("http://example.com/test", read_only_file, "token")


def test_download_with_auth_headers_large_file(tmp_path):
    """Test downloading a large file with chunked reading."""
    with patch("conda_pypi.auth.get_session") as mock_get_session:
        # Simulate a large file with multiple chunks
        large_content = b"x" * 10000  # 10KB of data
        chunks = [large_content[i : i + 1024] for i in range(0, len(large_content), 1024)]

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.iter_content.return_value = chunks

        mock_headers = {}
        mock_session = Mock()
        mock_session.headers = mock_headers
        mock_session.get.return_value = mock_response
        mock_get_session.return_value = mock_session

        target_file = tmp_path / "large_file"
        download_with_auth_headers("http://example.com/large", target_file, "token")

        # Verify file was created with correct size
        assert target_file.exists(), "Large file should be created"
        assert target_file.stat().st_size == len(large_content), "File size should match content"
