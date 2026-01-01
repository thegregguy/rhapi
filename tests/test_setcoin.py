"""
Unit tests for setcoin.py portfolio management.

Tests portfolio loading, saving, caching, and state updates.
"""

import pytest
import json
import os
import tempfile
import time
from unittest.mock import patch, Mock

import setcoin


@pytest.fixture
def temp_portfolio_file(tmp_path):
    """Create a temporary portfolio file."""
    portfolio_file = tmp_path / "portfolio.json"
    
    # Override the module-level constant
    original_file = setcoin.PORTFOLIO_FILE
    setcoin.PORTFOLIO_FILE = str(portfolio_file)
    
    yield str(portfolio_file)
    
    # Restore original
    setcoin.PORTFOLIO_FILE = original_file
    setcoin.invalidate_cache()


@pytest.fixture
def sample_portfolio():
    """Sample portfolio data."""
    return {
        "BTC-USD": {
            "exchange": "RH",
            "can_buy": True,
            "total_invested": 100.0,
            "last_reference_price": 50000.0,
            "profit_mult": 2.0,
            "dip_mult": 3.0,
            "last_buy_time": 0
        },
        "ETH-USDC": {
            "exchange": "CB",
            "can_buy": False,
            "total_invested": 0.0,
            "last_reference_price": 3000.0,
            "profit_mult": 3.0,
            "dip_mult": 3.0,
            "last_buy_time": 0
        }
    }


class TestLoadPortfolio:
    """Test portfolio loading."""
    
    def test_load_nonexistent_file(self, temp_portfolio_file):
        """Test loading when file doesn't exist returns empty dict."""
        setcoin.invalidate_cache()
        portfolio = setcoin.load_portfolio()
        assert portfolio == {}
    
    def test_load_existing_file(self, temp_portfolio_file, sample_portfolio):
        """Test loading existing portfolio file."""
        # Write sample portfolio
        with open(temp_portfolio_file, 'w') as f:
            json.dump(sample_portfolio, f)
        
        setcoin.invalidate_cache()
        portfolio = setcoin.load_portfolio()
        
        assert "BTC-USD" in portfolio
        assert portfolio["BTC-USD"]["exchange"] == "RH"
    
    def test_load_with_caching(self, temp_portfolio_file, sample_portfolio):
        """Test that caching works."""
        with open(temp_portfolio_file, 'w') as f:
            json.dump(sample_portfolio, f)
        
        setcoin.invalidate_cache()
        
        # First load
        portfolio1 = setcoin.load_portfolio()
        
        # Modify file directly
        sample_portfolio["DOGE-USD"] = {"exchange": "RH", "can_buy": True}
        with open(temp_portfolio_file, 'w') as f:
            json.dump(sample_portfolio, f)
        
        # Second load should return cached (within TTL)
        portfolio2 = setcoin.load_portfolio()
        
        # Should not have DOGE yet (cached)
        assert "DOGE-USD" not in portfolio2
        
        # Wait for cache to expire
        time.sleep(1.5)
        portfolio3 = setcoin.load_portfolio()
        
        # Should now have DOGE (cache expired)
        assert "DOGE-USD" in portfolio3
    
    def test_load_corrupted_file(self, temp_portfolio_file):
        """Test loading corrupted JSON file."""
        # Write invalid JSON
        with open(temp_portfolio_file, 'w') as f:
            f.write("not valid json {{{")
        
        setcoin.invalidate_cache()
        portfolio = setcoin.load_portfolio()
        
        # Should return empty dict on error
        assert portfolio == {}


class TestSavePortfolio:
    """Test portfolio saving."""
    
    def test_save_portfolio(self, temp_portfolio_file, sample_portfolio):
        """Test saving portfolio to disk."""
        setcoin.save_portfolio(sample_portfolio)
        
        # Read back and verify
        with open(temp_portfolio_file, 'r') as f:
            loaded = json.load(f)
        
        assert loaded == sample_portfolio
    
    def test_save_atomic(self, temp_portfolio_file, sample_portfolio):
        """Test that save is atomic (uses temp file)."""
        setcoin.save_portfolio(sample_portfolio)
        
        # Temp file should not exist after save
        temp_file = temp_portfolio_file + ".tmp"
        assert not os.path.exists(temp_file)
        
        # Main file should exist
        assert os.path.exists(temp_portfolio_file)
    
    def test_save_updates_cache(self, temp_portfolio_file, sample_portfolio):
        """Test that saving updates the cache."""
        setcoin.save_portfolio(sample_portfolio)
        
        # Load should return cached version immediately
        loaded = setcoin.load_portfolio()
        assert loaded == sample_portfolio


class TestUpdateCoinState:
    """Test updating coin state."""
    
    def test_update_existing_coin(self, temp_portfolio_file, sample_portfolio):
        """Test updating state of existing coin."""
        setcoin.save_portfolio(sample_portfolio)
        
        # Update BTC
        setcoin.update_coin_state("BTC-USD", {"can_buy": False, "total_invested": 200.0})
        
        # Verify update
        setcoin.invalidate_cache()
        portfolio = setcoin.load_portfolio()
        assert portfolio["BTC-USD"]["can_buy"] is False
        assert portfolio["BTC-USD"]["total_invested"] == 200.0
        
        # Other fields should remain unchanged
        assert portfolio["BTC-USD"]["exchange"] == "RH"
    
    def test_update_nonexistent_coin(self, temp_portfolio_file, sample_portfolio):
        """Test updating non-existent coin does nothing."""
        setcoin.save_portfolio(sample_portfolio)
        
        # Try to update non-existent coin
        setcoin.update_coin_state("DOGE-USD", {"can_buy": True})
        
        # Portfolio should be unchanged
        setcoin.invalidate_cache()
        portfolio = setcoin.load_portfolio()
        assert "DOGE-USD" not in portfolio
    
    def test_update_no_changes(self, temp_portfolio_file, sample_portfolio):
        """Test that update without changes doesn't write to disk."""
        setcoin.save_portfolio(sample_portfolio)
        
        # Get modification time
        mtime_before = os.path.getmtime(temp_portfolio_file)
        time.sleep(0.1)
        
        # Update with same values
        setcoin.update_coin_state("BTC-USD", {"can_buy": True})  # Already True
        
        # File should not be modified
        mtime_after = os.path.getmtime(temp_portfolio_file)
        assert mtime_before == mtime_after


class TestNormalizeSymbol:
    """Test symbol normalization."""
    
    def test_normalize_for_rh(self):
        """Test normalizing symbol for Robinhood."""
        assert setcoin.normalize_symbol("BTC", "RH") == "BTC-USD"
        assert setcoin.normalize_symbol("BTC-USDC", "RH") == "BTC-USD"
        assert setcoin.normalize_symbol("BTC-USD", "RH") == "BTC-USD"
    
    def test_normalize_for_cb(self):
        """Test normalizing symbol for Coinbase."""
        assert setcoin.normalize_symbol("ETH", "CB") == "ETH-USDC"
        assert setcoin.normalize_symbol("ETH-USD", "CB") == "ETH-USDC"
        assert setcoin.normalize_symbol("ETH-USDC", "CB") == "ETH-USDC"


class TestAddCoinInteractive:
    """Test adding coins to portfolio."""
    
    def test_add_new_coin_rh(self, temp_portfolio_file):
        """Test adding new coin to Robinhood portfolio."""
        setcoin.save_portfolio({})
        
        result = setcoin.add_coin_interactive("BTC", "RH")
        
        assert result is True
        
        setcoin.invalidate_cache()
        portfolio = setcoin.load_portfolio()
        assert "BTC-USD" in portfolio
        assert portfolio["BTC-USD"]["exchange"] == "RH"
        assert portfolio["BTC-USD"]["can_buy"] is False  # Default
    
    def test_add_new_coin_cb(self, temp_portfolio_file):
        """Test adding new coin to Coinbase portfolio."""
        setcoin.save_portfolio({})
        
        result = setcoin.add_coin_interactive("ETH", "CB")
        
        assert result is True
        
        setcoin.invalidate_cache()
        portfolio = setcoin.load_portfolio()
        assert "ETH-USDC" in portfolio
        assert portfolio["ETH-USDC"]["exchange"] == "CB"
    
    def test_add_existing_coin(self, temp_portfolio_file, sample_portfolio):
        """Test adding coin that already exists."""
        setcoin.save_portfolio(sample_portfolio)
        
        result = setcoin.add_coin_interactive("BTC", "RH")
        
        assert result is False
        
        # Portfolio should be unchanged
        setcoin.invalidate_cache()
        portfolio = setcoin.load_portfolio()
        assert portfolio["BTC-USD"]["total_invested"] == 100.0  # Original value


class TestAuditPortfolio:
    """Test portfolio audit functionality."""
    
    @patch('setcoin.get_unified_holdings')
    def test_audit_adds_new_holdings(self, mock_holdings, temp_portfolio_file):
        """Test audit adds newly discovered holdings."""
        # Start with empty portfolio
        setcoin.save_portfolio({})
        
        # Mock holdings
        mock_holdings.return_value = [
            {"symbol": "BTC-USD", "qty": 0.001, "exchange": "RH"},
            {"symbol": "ETH-USDC", "qty": 0.1, "exchange": "CB"}
        ]
        
        # Run audit
        setcoin.audit_portfolio()
        
        # Check portfolio was updated
        setcoin.invalidate_cache()
        portfolio = setcoin.load_portfolio()
        
        assert "BTC-USD" in portfolio
        assert "ETH-USDC" in portfolio
        assert portfolio["BTC-USD"]["exchange"] == "RH"
    
    @patch('setcoin.get_unified_holdings')
    def test_audit_preserves_existing_settings(
        self, mock_holdings, temp_portfolio_file, sample_portfolio
    ):
        """Test audit preserves existing coin settings."""
        setcoin.save_portfolio(sample_portfolio)
        
        # Mock holdings
        mock_holdings.return_value = [
            {"symbol": "BTC-USD", "qty": 0.001, "exchange": "RH"}
        ]
        
        # Run audit
        setcoin.audit_portfolio()
        
        # Check settings preserved
        setcoin.invalidate_cache()
        portfolio = setcoin.load_portfolio()
        
        assert portfolio["BTC-USD"]["can_buy"] is True  # Original setting
        assert portfolio["BTC-USD"]["total_invested"] == 100.0  # Original
    
    @patch('setcoin.get_unified_holdings')
    def test_audit_handles_empty_holdings(self, mock_holdings, temp_portfolio_file):
        """Test audit with no holdings."""
        setcoin.save_portfolio({})
        mock_holdings.return_value = []
        
        # Should not raise exception
        setcoin.audit_portfolio()


class TestCacheInvalidation:
    """Test cache invalidation."""
    
    def test_invalidate_cache(self, temp_portfolio_file, sample_portfolio):
        """Test explicit cache invalidation."""
        setcoin.save_portfolio(sample_portfolio)
        
        # Load to populate cache
        portfolio1 = setcoin.load_portfolio()
        
        # Modify file
        sample_portfolio["NEW-USD"] = {"exchange": "RH"}
        with open(temp_portfolio_file, 'w') as f:
            json.dump(sample_portfolio, f)
        
        # Invalidate cache
        setcoin.invalidate_cache()
        
        # Load should see new data
        portfolio2 = setcoin.load_portfolio()
        assert "NEW-USD" in portfolio2
