"""
Unit tests for setcoin portfolio management module.

Tests cover:
- Portfolio loading and saving
- Caching behavior
- Symbol normalization
- State updates
- Change detection
"""

import pytest
import json
import os
import tempfile
from unittest.mock import patch, Mock
import setcoin


@pytest.fixture
def temp_portfolio_file(tmp_path):
    """Create a temporary portfolio file."""
    portfolio_file = tmp_path / "portfolio.json"
    original_file = setcoin.PORTFOLIO_FILE
    setcoin.PORTFOLIO_FILE = str(portfolio_file)
    yield str(portfolio_file)
    setcoin.PORTFOLIO_FILE = original_file
    # Clear cache
    setcoin._portfolio_cache = None
    setcoin._portfolio_hash = None


@pytest.fixture
def sample_portfolio():
    """Create a sample portfolio."""
    return {
        "BTC-USD": {
            "exchange": "RH",
            "can_buy": True,
            "total_invested": 100.0,
            "last_reference_price": 50000.0,
            "last_buy_time": 1234567890,
            "profit_mult": 2.0,
            "dip_mult": 3.0
        },
        "ETH-USDC": {
            "exchange": "CB",
            "can_buy": False,
            "total_invested": 50.0,
            "last_reference_price": 3000.0,
            "last_buy_time": 1234567890,
            "profit_mult": 2.0,
            "dip_mult": 3.0
        }
    }


class TestLoadPortfolio:
    """Test portfolio loading functionality."""
    
    def test_load_nonexistent_portfolio(self, temp_portfolio_file):
        """Test loading when portfolio file doesn't exist."""
        portfolio = setcoin.load_portfolio()
        assert portfolio == {}
    
    def test_load_existing_portfolio(self, temp_portfolio_file, sample_portfolio):
        """Test loading existing portfolio file."""
        # Write sample portfolio
        with open(temp_portfolio_file, 'w') as f:
            json.dump(sample_portfolio, f)
        
        portfolio = setcoin.load_portfolio()
        assert portfolio == sample_portfolio
        assert "BTC-USD" in portfolio
        assert "ETH-USDC" in portfolio
    
    def test_load_corrupted_portfolio(self, temp_portfolio_file):
        """Test loading corrupted portfolio file."""
        # Write invalid JSON
        with open(temp_portfolio_file, 'w') as f:
            f.write("invalid json content")
        
        portfolio = setcoin.load_portfolio()
        assert portfolio == {}


class TestSavePortfolio:
    """Test portfolio saving functionality."""
    
    def test_save_portfolio_creates_file(self, temp_portfolio_file, sample_portfolio):
        """Test saving portfolio creates file."""
        setcoin.save_portfolio(sample_portfolio)
        
        assert os.path.exists(temp_portfolio_file)
        
        with open(temp_portfolio_file, 'r') as f:
            saved = json.load(f)
        
        assert saved == sample_portfolio
    
    def test_save_portfolio_atomic(self, temp_portfolio_file, sample_portfolio):
        """Test portfolio save is atomic (uses temp file)."""
        setcoin.save_portfolio(sample_portfolio)
        
        # Temp file should be cleaned up
        temp_file = temp_portfolio_file + ".tmp"
        assert not os.path.exists(temp_file)
    
    def test_save_portfolio_skips_unchanged(self, temp_portfolio_file, sample_portfolio):
        """Test save skips writing when data hasn't changed."""
        # Save once
        setcoin.save_portfolio(sample_portfolio)
        
        # Get modification time
        mtime1 = os.path.getmtime(temp_portfolio_file)
        
        # Save again with same data
        import time
        time.sleep(0.01)  # Ensure time difference if file is written
        setcoin.save_portfolio(sample_portfolio)
        
        # Modification time should be the same (file not rewritten)
        mtime2 = os.path.getmtime(temp_portfolio_file)
        assert mtime1 == mtime2


class TestCaching:
    """Test portfolio caching behavior."""
    
    def test_cache_populated_on_load(self, temp_portfolio_file, sample_portfolio):
        """Test cache is populated when portfolio is loaded."""
        with open(temp_portfolio_file, 'w') as f:
            json.dump(sample_portfolio, f)
        
        # Clear cache
        setcoin._portfolio_cache = None
        
        portfolio = setcoin.load_portfolio()
        
        # Verify cache is populated
        assert setcoin._portfolio_cache is not None
        assert setcoin._portfolio_hash is not None
    
    def test_get_portfolio_returns_cached(self, temp_portfolio_file, sample_portfolio):
        """Test get_portfolio returns cached version."""
        with open(temp_portfolio_file, 'w') as f:
            json.dump(sample_portfolio, f)
        
        # Load once to populate cache
        setcoin.load_portfolio()
        
        # Get from cache (should not read file again)
        portfolio = setcoin.get_portfolio()
        
        assert portfolio == sample_portfolio
    
    def test_get_portfolio_loads_if_no_cache(self, temp_portfolio_file, sample_portfolio):
        """Test get_portfolio loads from disk if cache is empty."""
        with open(temp_portfolio_file, 'w') as f:
            json.dump(sample_portfolio, f)
        
        # Clear cache
        setcoin._portfolio_cache = None
        
        portfolio = setcoin.get_portfolio()
        
        assert portfolio == sample_portfolio


class TestSymbolNormalization:
    """Test symbol normalization helper."""
    
    def test_normalize_symbol_rh(self):
        """Test normalizing symbols for Robinhood."""
        assert setcoin.normalize_symbol("BTC", "RH") == "BTC-USD"
        assert setcoin.normalize_symbol("BTC-USD", "RH") == "BTC-USD"
        assert setcoin.normalize_symbol("BTC-USDC", "RH") == "BTC-USD"
        assert setcoin.normalize_symbol("btc", "RH") == "BTC-USD"
    
    def test_normalize_symbol_cb(self):
        """Test normalizing symbols for Coinbase."""
        assert setcoin.normalize_symbol("ETH", "CB") == "ETH-USDC"
        assert setcoin.normalize_symbol("ETH-USDC", "CB") == "ETH-USDC"
        assert setcoin.normalize_symbol("ETH-USD", "CB") == "ETH-USDC"
        assert setcoin.normalize_symbol("eth", "CB") == "ETH-USDC"


class TestUpdateCoinState:
    """Test coin state update functionality."""
    
    def test_update_coin_state_changes_data(self, temp_portfolio_file, sample_portfolio):
        """Test updating coin state modifies portfolio."""
        setcoin.save_portfolio(sample_portfolio)
        
        updates = {
            "last_seen_price": 51000.0,
            "last_profit_pct": 0.05
        }
        
        setcoin.update_coin_state("BTC-USD", updates)
        
        portfolio = setcoin.load_portfolio()
        assert portfolio["BTC-USD"]["last_seen_price"] == 51000.0
        assert portfolio["BTC-USD"]["last_profit_pct"] == 0.05
    
    def test_update_coin_state_nonexistent_coin(self, temp_portfolio_file, sample_portfolio):
        """Test updating nonexistent coin doesn't crash."""
        setcoin.save_portfolio(sample_portfolio)
        
        updates = {"last_seen_price": 1000.0}
        
        # Should not raise exception
        setcoin.update_coin_state("DOGE-USD", updates)
    
    def test_update_coin_state_skips_if_no_change(self, temp_portfolio_file, sample_portfolio):
        """Test update skips save if data hasn't changed."""
        setcoin.save_portfolio(sample_portfolio)
        
        # Get modification time
        mtime1 = os.path.getmtime(temp_portfolio_file)
        
        # Update with same values
        import time
        time.sleep(0.01)
        updates = {
            "total_invested": 100.0,  # Same as original
        }
        
        setcoin.update_coin_state("BTC-USD", updates)
        
        # File should not be rewritten
        mtime2 = os.path.getmtime(temp_portfolio_file)
        assert mtime1 == mtime2


class TestAddCoinInteractive:
    """Test adding coins to portfolio."""
    
    def test_add_new_coin_rh(self, temp_portfolio_file):
        """Test adding a new coin for Robinhood."""
        setcoin.save_portfolio({})
        
        result = setcoin.add_coin_interactive("BTC", "RH")
        
        assert result is True
        
        portfolio = setcoin.load_portfolio()
        assert "BTC-USD" in portfolio
        assert portfolio["BTC-USD"]["exchange"] == "RH"
        assert portfolio["BTC-USD"]["can_buy"] is False
        assert portfolio["BTC-USD"]["total_invested"] == 0.0
    
    def test_add_new_coin_cb(self, temp_portfolio_file):
        """Test adding a new coin for Coinbase."""
        setcoin.save_portfolio({})
        
        result = setcoin.add_coin_interactive("ETH", "CB")
        
        assert result is True
        
        portfolio = setcoin.load_portfolio()
        assert "ETH-USDC" in portfolio
        assert portfolio["ETH-USDC"]["exchange"] == "CB"
    
    def test_add_duplicate_coin(self, temp_portfolio_file, sample_portfolio):
        """Test adding duplicate coin returns False."""
        setcoin.save_portfolio(sample_portfolio)
        
        result = setcoin.add_coin_interactive("BTC", "RH")
        
        assert result is False
    
    def test_add_coin_normalizes_symbol(self, temp_portfolio_file):
        """Test adding coin normalizes symbol based on exchange."""
        setcoin.save_portfolio({})
        
        # Add with wrong suffix
        result = setcoin.add_coin_interactive("BTC-USDC", "RH")
        
        assert result is True
        
        portfolio = setcoin.load_portfolio()
        # Should be normalized to -USD for RH
        assert "BTC-USD" in portfolio
        assert "BTC-USDC" not in portfolio


class TestAuditPortfolio:
    """Test portfolio audit functionality."""
    
    @patch('setcoin.get_unified_holdings')
    def test_audit_adds_missing_coins(self, mock_holdings, temp_portfolio_file):
        """Test audit adds coins found in holdings."""
        setcoin.save_portfolio({})
        
        mock_holdings.return_value = [
            {"symbol": "BTC-USD", "qty": 0.001, "exchange": "RH"},
            {"symbol": "ETH-USDC", "qty": 0.002, "exchange": "CB"}
        ]
        
        setcoin.audit_portfolio()
        
        portfolio = setcoin.load_portfolio()
        assert "BTC-USD" in portfolio
        assert "ETH-USDC" in portfolio
        assert portfolio["BTC-USD"]["exchange"] == "RH"
        assert portfolio["ETH-USDC"]["exchange"] == "CB"
    
    @patch('setcoin.get_unified_holdings')
    def test_audit_updates_exchange(self, mock_holdings, temp_portfolio_file, sample_portfolio):
        """Test audit ensures exchange tag is correct."""
        setcoin.save_portfolio(sample_portfolio)
        
        mock_holdings.return_value = [
            {"symbol": "BTC-USD", "qty": 0.001, "exchange": "RH"}
        ]
        
        setcoin.audit_portfolio()
        
        portfolio = setcoin.load_portfolio()
        assert portfolio["BTC-USD"]["exchange"] == "RH"
    
    @patch('setcoin.get_unified_holdings')
    def test_audit_preserves_existing_settings(self, mock_holdings, temp_portfolio_file, sample_portfolio):
        """Test audit preserves existing coin settings."""
        setcoin.save_portfolio(sample_portfolio)
        
        mock_holdings.return_value = [
            {"symbol": "BTC-USD", "qty": 0.001, "exchange": "RH"}
        ]
        
        setcoin.audit_portfolio()
        
        portfolio = setcoin.load_portfolio()
        # Should preserve original settings
        assert portfolio["BTC-USD"]["can_buy"] is True
        assert portfolio["BTC-USD"]["total_invested"] == 100.0
