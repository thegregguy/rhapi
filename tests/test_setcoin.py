"""
Unit tests for setcoin.py module.

Tests portfolio persistence and management functions.
"""

import pytest
import json
import os
import tempfile
from unittest.mock import Mock, patch, mock_open
from setcoin import (
    load_portfolio,
    save_portfolio,
    update_coin_state,
    add_coin_interactive,
    DEFAULT_SETTINGS
)


@pytest.fixture
def temp_portfolio_file():
    """Create a temporary portfolio file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        temp_path = f.name
        json.dump({}, f)
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


def test_load_portfolio_empty(temp_portfolio_file):
    """Test loading an empty portfolio."""
    with patch('setcoin.PORTFOLIO_FILE', temp_portfolio_file):
        portfolio = load_portfolio()
        assert portfolio == {}


def test_load_portfolio_with_data(temp_portfolio_file):
    """Test loading a portfolio with data."""
    test_data = {
        'BTC-USD': {
            'exchange': 'RH',
            'can_buy': True,
            'total_invested': 100.0
        }
    }
    
    with open(temp_portfolio_file, 'w') as f:
        json.dump(test_data, f)
    
    with patch('setcoin.PORTFOLIO_FILE', temp_portfolio_file):
        portfolio = load_portfolio()
        assert 'BTC-USD' in portfolio
        assert portfolio['BTC-USD']['exchange'] == 'RH'


def test_load_portfolio_missing_file():
    """Test loading portfolio when file doesn't exist."""
    with patch('setcoin.PORTFOLIO_FILE', '/tmp/nonexistent_file.json'):
        with patch('os.path.exists', return_value=False):
            portfolio = load_portfolio()
            assert portfolio == {}


def test_save_portfolio(temp_portfolio_file):
    """Test saving portfolio data."""
    test_data = {
        'ETH-USDC': {
            'exchange': 'CB',
            'can_buy': False,
            'total_invested': 200.0
        }
    }
    
    with patch('setcoin.PORTFOLIO_FILE', temp_portfolio_file):
        save_portfolio(test_data)
    
    # Verify file was written
    with open(temp_portfolio_file, 'r') as f:
        saved_data = json.load(f)
        assert 'ETH-USDC' in saved_data
        assert saved_data['ETH-USDC']['exchange'] == 'CB'


def test_save_portfolio_atomic_write(temp_portfolio_file):
    """Test that save_portfolio uses atomic write (temp file + replace)."""
    test_data = {'test': 'data'}
    
    with patch('setcoin.PORTFOLIO_FILE', temp_portfolio_file):
        with patch('os.replace') as mock_replace:
            save_portfolio(test_data)
            # Should call os.replace for atomic write
            assert mock_replace.called


def test_update_coin_state(temp_portfolio_file):
    """Test updating a coin's state."""
    initial_data = {
        'BTC-USD': {
            'exchange': 'RH',
            'can_buy': True,
            'total_invested': 100.0,
            'last_seen_price': 50000.0
        }
    }
    
    with open(temp_portfolio_file, 'w') as f:
        json.dump(initial_data, f)
    
    with patch('setcoin.PORTFOLIO_FILE', temp_portfolio_file):
        update_coin_state('BTC-USD', {'last_seen_price': 51000.0})
        
        # Verify update
        portfolio = load_portfolio()
        assert portfolio['BTC-USD']['last_seen_price'] == 51000.0
        # Other fields should remain unchanged
        assert portfolio['BTC-USD']['total_invested'] == 100.0


def test_update_coin_state_nonexistent(temp_portfolio_file):
    """Test updating a coin that doesn't exist in portfolio."""
    with open(temp_portfolio_file, 'w') as f:
        json.dump({}, f)
    
    with patch('setcoin.PORTFOLIO_FILE', temp_portfolio_file):
        # Should not raise error, just do nothing
        update_coin_state('DOGE-USD', {'last_seen_price': 0.10})
        
        # Coin should not be added
        portfolio = load_portfolio()
        assert 'DOGE-USD' not in portfolio


def test_add_coin_interactive_rh(temp_portfolio_file):
    """Test adding a new RH coin."""
    with open(temp_portfolio_file, 'w') as f:
        json.dump({}, f)
    
    with patch('setcoin.PORTFOLIO_FILE', temp_portfolio_file):
        result = add_coin_interactive('BTC', 'RH')
        
        assert result is True
        portfolio = load_portfolio()
        assert 'BTC-USD' in portfolio
        assert portfolio['BTC-USD']['exchange'] == 'RH'
        assert portfolio['BTC-USD']['can_buy'] == False  # Default


def test_add_coin_interactive_cb(temp_portfolio_file):
    """Test adding a new CB coin."""
    with open(temp_portfolio_file, 'w') as f:
        json.dump({}, f)
    
    with patch('setcoin.PORTFOLIO_FILE', temp_portfolio_file):
        result = add_coin_interactive('ETH', 'CB')
        
        assert result is True
        portfolio = load_portfolio()
        assert 'ETH-USDC' in portfolio
        assert portfolio['ETH-USDC']['exchange'] == 'CB'


def test_add_coin_interactive_duplicate(temp_portfolio_file):
    """Test adding a duplicate coin returns False."""
    initial_data = {
        'BTC-USD': {
            'exchange': 'RH',
            'can_buy': True
        }
    }
    
    with open(temp_portfolio_file, 'w') as f:
        json.dump(initial_data, f)
    
    with patch('setcoin.PORTFOLIO_FILE', temp_portfolio_file):
        result = add_coin_interactive('BTC', 'RH')
        
        assert result is False
        # Portfolio should remain unchanged
        portfolio = load_portfolio()
        assert portfolio['BTC-USD']['can_buy'] == True


def test_add_coin_interactive_suffix_normalization(temp_portfolio_file):
    """Test that coin symbols are normalized with correct suffix."""
    with open(temp_portfolio_file, 'w') as f:
        json.dump({}, f)
    
    with patch('setcoin.PORTFOLIO_FILE', temp_portfolio_file):
        # Add with -USDC suffix but to RH (should convert to -USD)
        result = add_coin_interactive('BTC-USDC', 'RH')
        
        assert result is True
        portfolio = load_portfolio()
        assert 'BTC-USD' in portfolio
        assert 'BTC-USDC' not in portfolio


def test_default_settings_structure():
    """Test that DEFAULT_SETTINGS has expected structure."""
    assert 'can_buy' in DEFAULT_SETTINGS
    assert 'profit_mult' in DEFAULT_SETTINGS
    assert 'dip_mult' in DEFAULT_SETTINGS
    assert 'last_buy_time' in DEFAULT_SETTINGS
    
    # Verify defaults
    assert DEFAULT_SETTINGS['can_buy'] is False
    assert DEFAULT_SETTINGS['last_buy_time'] == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
