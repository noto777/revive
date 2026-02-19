import pytest
import os
import json
from unittest.mock import patch, mock_open, MagicMock
from adapter_alpaca import AlpacaClient

# Mock data
MOCK_CREDS = {
    "key_id": "TEST_KEY",
    "secret_key": "TEST_SECRET",
    "endpoint": "https://paper-api.alpaca.markets"
}

@pytest.fixture
def mock_creds_file():
    with patch("builtins.open", mock_open(read_data=json.dumps(MOCK_CREDS))) as m:
        yield m

def test_init_with_direct_creds():
    """Test initialization with direct API key and secret."""
    client = AlpacaClient(api_key="DIRECT_KEY", secret_key="DIRECT_SECRET")
    assert client.api_key == "DIRECT_KEY"
    assert client.secret_key == "DIRECT_SECRET"
    assert client.base_url == "https://paper-api.alpaca.markets"

def test_init_with_user_id(mock_creds_file):
    """Test initialization with user_id loads from file."""
    with patch("os.path.exists", return_value=True):
        client = AlpacaClient(user_id="test_user")
        assert client.api_key == "TEST_KEY"
        assert client.secret_key == "TEST_SECRET"
        assert client.user_id == "test_user"

def test_init_fallback_to_default(mock_creds_file):
    """Test fallback to alpaca_cred.json if user file missing."""
    # First call (user file) returns False, second call (default file) returns True
    with patch("os.path.exists", side_effect=[False, True]):
        client = AlpacaClient(user_id="missing_user")
        assert client.api_key == "TEST_KEY"

def test_init_missing_args():
    """Test error when no args provided."""
    with pytest.raises(ValueError):
        AlpacaClient()

def test_credential_load_failure():
    """Test error handling when cred file is unreadable."""
    with patch("builtins.open", side_effect=IOError("File not found")):
        with patch("os.path.exists", return_value=True):
            with pytest.raises(Exception) as excinfo:
                AlpacaClient(user_id="broken_user")
            assert "Failed to load Alpaca credentials" in str(excinfo.value)
