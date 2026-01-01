"""
Unit tests for setcoin module
"""
import pytest
import json
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock
from setcoin import (
    load_portfolio,
    save_portfolio,
    update_coin_state,
    add_coin_interactive,
    normalize_symbol,
    PORTFOLIO_FILE
)


@pytest.fixture
def temp_portfolio_file(monkeypatch):
    """Create a temporary portfolio file for testing"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        temp_file = f.name
        json.dump({}, f)
    
    # Monkey patch the PORTFOLIO_FILE
    import setcoin
    monkeypatch.setattr(setcoin, 'PORTFOLIO_FILE', temp_file)
    
    yield temp_file
    
    # Cleanup
    if os.path.exists(temp_file):
        os.remove(temp_file)
    if os.path.exists(temp_file + ".tmp"):
        os.remove(temp_file + ".tmp")


def test_normalize_symbol_robinhood():
    """Test symbol normalization for Robinhood"""
    assert normalize_symbol("BTC", "RH") == "BTC-USD"
    assert normalize_symbol("BTC-USDC", "RH") == "BTC-USD"
    assert normalize_symbol("BTC-USD", "RH") == "BTC-USD"
    assert normalize_symbol("btc", "RH") == "BTC-USD"


def test_normalize_symbol_coinbase():
    """Test symbol normalization for Coinbase"""
    assert normalize_symbol("BTC", "CB") == "BTC-USDC"
    assert normalize_symbol("BTC-USD", "CB") == "BTC-USDC"
    assert normalize_symbol("BTC-USDC", "CB") == "BTC-USDC"
    assert normalize_symbol("eth", "CB") == "ETH-USDC"


def test_load_portfolio_empty(temp_portfolio_file):
    """Test loading an empty portfolio"""
    portfolio = load_portfolio(use_cache=False)
    assert portfolio == {}


def test_save_and_load_portfolio(temp_portfolio_file):
    """Test saving and loading portfolio"""
    test_data = {
        "BTC-USD": {
            "exchange": "RH",
            "can_buy": True,
            "total_invested": 100.0
        }
    }
    
    save_portfolio(test_data)
    loaded = load_portfolio(use_cache=False)
    
    assert loaded == test_data
    assert "BTC-USD" in loaded
    assert loaded["BTC-USD"]["total_invested"] == 100.0


def test_save_portfolio_atomic(temp_portfolio_file):
    """Test that save_portfolio uses atomic file operations"""
    test_data = {"BTC-USD": {"exchange": "RH"}}
    
    save_portfolio(test_data)
    
    # Verify the temp file is removed after save
    import setcoin
    temp_file = setcoin.PORTFOLIO_FILE + ".tmp"
    assert not os.path.exists(temp_file)


def test_update_coin_state(temp_portfolio_file):
    """Test updating coin state"""
    # First save a portfolio
    initial_data = {
        "BTC-USD": {
            "exchange": "RH",
            "can_buy": False,
            "total_invested": 0.0
        }
    }
    save_portfolio(initial_data)
    
    # Update the state
    update_coin_state("BTC-USD", {"can_buy": True, "total_invested": 50.0})
    
    # Verify update
    loaded = load_portfolio(use_cache=False)
    assert loaded["BTC-USD"]["can_buy"] is True
    assert loaded["BTC-USD"]["total_invested"] == 50.0


def test_add_coin_interactive_new(temp_portfolio_file):
    """Test adding a new coin"""
    result = add_coin_interactive("BTC", "RH")
    
    assert result is True
    
    portfolio = load_portfolio(use_cache=False)
    assert "BTC-USD" in portfolio
    assert portfolio["BTC-USD"]["exchange"] == "RH"
    assert portfolio["BTC-USD"]["can_buy"] is False


def test_add_coin_interactive_existing(temp_portfolio_file):
    """Test adding an existing coin returns False"""
    # Add first time
    add_coin_interactive("BTC", "RH")
    
    # Try to add again
    result = add_coin_interactive("BTC", "RH")
    assert result is False


def test_add_coin_interactive_normalization(temp_portfolio_file):
    """Test that symbols are normalized when adding"""
    add_coin_interactive("BTC", "RH")
    portfolio = load_portfolio(use_cache=False)
    
    # Should be normalized to BTC-USD
    assert "BTC-USD" in portfolio
    assert "BTC" not in portfolio


def test_portfolio_caching():
    """Test portfolio caching mechanism"""
    with patch('setcoin.os.path.exists', return_value=False):
        # First call
        p1 = load_portfolio(use_cache=True)
        
        # Second call should use cache
        p2 = load_portfolio(use_cache=True)
        
        assert p1 is not p2  # Should be copies, not same object
        assert p1 == p2


def test_audit_portfolio(temp_portfolio_file):
    """Test portfolio audit functionality"""
    from setcoin import audit_portfolio
    
    # We need to patch bot.get_unified_holdings since audit_portfolio imports it
    with patch('bot.get_unified_holdings') as mock_bot_holdings:
        mock_bot_holdings.return_value = [
            {'symbol': 'BTC-USD', 'qty': 1.5, 'exchange': 'RH'},
            {'symbol': 'ETH-USDC', 'qty': 10.0, 'exchange': 'CB'}
        ]
        
        audit_portfolio()
        
        portfolio = load_portfolio(use_cache=False)
        
        assert 'BTC-USD' in portfolio
        assert 'ETH-USDC' in portfolio
        assert portfolio['BTC-USD']['exchange'] == 'RH'
        assert portfolio['ETH-USDC']['exchange'] == 'CB'


def test_thread_safety():
    """Test that update operations are thread-safe"""
    import threading
    import setcoin
    
    # This is a basic test to ensure the lock exists
    assert hasattr(setcoin, '_portfolio_lock')
    # threading.Lock is actually a function that returns a lock object
    # So we check if it's a lock-like object by checking for acquire/release methods
    assert hasattr(setcoin._portfolio_lock, 'acquire')
    assert hasattr(setcoin._portfolio_lock, 'release')
