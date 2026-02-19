import pytest
import argparse
from unittest.mock import patch, MagicMock
from main_saas import IronHandBot

@pytest.fixture
def mock_alpaca_client():
    with patch("main_saas.AlpacaClient") as MockClient:
        yield MockClient

def test_bot_init_with_user_id(mock_alpaca_client):
    """Test initializing bot with a specific user_id."""
    # Mock open for config loading inside IronHandBot if needed, 
    # but IronHandBot now uses AlpacaClient(user_id=...) directly.
    # We might need to mock open if IronHandBot reads other configs.
    
    # Based on my code, IronHandBot.__init__ does:
    # self.client = AlpacaClient(user_id=self.user_id)
    
    bot = IronHandBot(user_id="test_user")
    
    assert bot.user_id == "test_user"
    assert bot.state_file == "user_test_user_bot_state.json"
    mock_alpaca_client.assert_called_with(user_id="test_user")

def test_bot_init_legacy_support(mock_alpaca_client):
    """Test that we can still init via CLI args logic flow."""
    # This simulates how main block uses it
    args = argparse.Namespace(user_id="legacy_user")
    bot = IronHandBot(user_id=args.user_id)
    
    assert bot.user_id == "legacy_user"
    mock_alpaca_client.assert_called_with(user_id="legacy_user")
