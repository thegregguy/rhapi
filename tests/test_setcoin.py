"""
Unit tests for setcoin module.
"""
import unittest
import os
import json
import tempfile
from unittest.mock import patch, Mock

# We need to set up the test environment before importing setcoin
TEST_PORTFOLIO_FILE = None


class TestSetcoin(unittest.TestCase):
    """Tests for setcoin.py load/save/update functionality."""
    
    def setUp(self):
        """Set up test fixtures with temporary file."""
        # Create a temporary file for testing
        self.temp_fd, self.temp_path = tempfile.mkstemp(suffix='.json')
        
        # Patch PORTFOLIO_FILE in setcoin module
        import setcoin
        self.original_portfolio_file = setcoin.PORTFOLIO_FILE
        setcoin.PORTFOLIO_FILE = self.temp_path
        
        # Clear cache
        setcoin.clear_portfolio_cache()
    
    def tearDown(self):
        """Clean up temporary files."""
        import setcoin
        setcoin.PORTFOLIO_FILE = self.original_portfolio_file
        setcoin.clear_portfolio_cache()
        
        # Close and remove temp file
        try:
            os.close(self.temp_fd)
        except:
            pass
        
        if os.path.exists(self.temp_path):
            os.remove(self.temp_path)
        
        # Also remove .tmp file if exists
        tmp_file = self.temp_path + ".tmp"
        if os.path.exists(tmp_file):
            os.remove(tmp_file)
    
    def test_load_empty_portfolio(self):
        """Test loading portfolio when file doesn't exist."""
        from setcoin import load_portfolio
        
        # Remove the temp file
        os.remove(self.temp_path)
        
        portfolio = load_portfolio()
        self.assertEqual(portfolio, {})
    
    def test_save_and_load_portfolio(self):
        """Test saving and loading portfolio."""
        from setcoin import save_portfolio, load_portfolio
        
        test_data = {
            "BTC-USD": {
                "exchange": "RH",
                "can_buy": True,
                "total_invested": 100.0,
                "last_reference_price": 50000.0
            }
        }
        
        save_portfolio(test_data, force=True)
        loaded = load_portfolio()
        
        self.assertEqual(loaded, test_data)
    
    def test_save_portfolio_atomic(self):
        """Test that save_portfolio is atomic (uses temp file)."""
        from setcoin import save_portfolio
        import setcoin
        
        test_data = {"TEST-USD": {"value": 123}}
        save_portfolio(test_data, force=True)
        
        # Check that temp file was cleaned up
        tmp_file = setcoin.PORTFOLIO_FILE + ".tmp"
        self.assertFalse(os.path.exists(tmp_file))
        
        # Check final file exists and has correct data
        self.assertTrue(os.path.exists(setcoin.PORTFOLIO_FILE))
        with open(setcoin.PORTFOLIO_FILE, 'r') as f:
            loaded = json.load(f)
        self.assertEqual(loaded, test_data)
    
    def test_save_portfolio_no_changes(self):
        """Test that save_portfolio skips save when no changes."""
        from setcoin import save_portfolio, load_portfolio
        
        test_data = {"BTC-USD": {"value": 100}}
        save_portfolio(test_data, force=True)
        
        # Get modification time
        mtime1 = os.path.getmtime(self.temp_path)
        
        # Try to save same data without force
        import time
        time.sleep(0.1)  # Ensure time difference
        save_portfolio(test_data, force=False)
        
        # Modification time should be unchanged
        mtime2 = os.path.getmtime(self.temp_path)
        self.assertEqual(mtime1, mtime2)
    
    def test_update_coin_state(self):
        """Test updating coin state."""
        from setcoin import save_portfolio, update_coin_state, load_portfolio
        
        # Set up initial portfolio
        initial = {
            "BTC-USD": {
                "exchange": "RH",
                "can_buy": False,
                "total_invested": 100.0
            }
        }
        save_portfolio(initial, force=True)
        
        # Update state
        update_coin_state("BTC-USD", {"can_buy": True, "last_seen_price": 50000.0})
        
        # Verify update
        updated = load_portfolio()
        self.assertEqual(updated["BTC-USD"]["can_buy"], True)
        self.assertEqual(updated["BTC-USD"]["last_seen_price"], 50000.0)
        self.assertEqual(updated["BTC-USD"]["total_invested"], 100.0)  # Unchanged
    
    def test_normalize_symbol_rh(self):
        """Test symbol normalization for Robinhood."""
        from setcoin import normalize_symbol
        
        self.assertEqual(normalize_symbol("BTC", "RH"), "BTC-USD")
        self.assertEqual(normalize_symbol("BTC-USD", "RH"), "BTC-USD")
        self.assertEqual(normalize_symbol("BTC-USDC", "RH"), "BTC-USD")
    
    def test_normalize_symbol_cb(self):
        """Test symbol normalization for Coinbase."""
        from setcoin import normalize_symbol
        
        self.assertEqual(normalize_symbol("BTC", "CB"), "BTC-USDC")
        self.assertEqual(normalize_symbol("BTC-USDC", "CB"), "BTC-USDC")
        self.assertEqual(normalize_symbol("BTC-USD", "CB"), "BTC-USDC")
    
    def test_portfolio_caching(self):
        """Test portfolio caching functionality."""
        from setcoin import load_portfolio, clear_portfolio_cache, save_portfolio
        
        # Save initial data
        test_data = {"BTC-USD": {"value": 100}}
        save_portfolio(test_data, force=True)
        
        # Load with cache
        data1 = load_portfolio(use_cache=True)
        
        # Modify file directly (bypassing cache)
        with open(self.temp_path, 'w') as f:
            json.dump({"BTC-USD": {"value": 200}}, f)
        
        # Load with cache - should return cached value
        data2 = load_portfolio(use_cache=True)
        self.assertEqual(data2, data1)  # Should be cached
        
        # Clear cache and reload
        clear_portfolio_cache()
        data3 = load_portfolio(use_cache=False)
        self.assertEqual(data3["BTC-USD"]["value"], 200)  # Should be new value
    
    def test_add_coin_interactive(self):
        """Test adding a coin interactively."""
        from setcoin import add_coin_interactive, load_portfolio
        
        # Add a new coin
        result = add_coin_interactive("BTC", "RH")
        self.assertTrue(result)
        
        # Verify it was added
        portfolio = load_portfolio()
        self.assertIn("BTC-USD", portfolio)
        self.assertEqual(portfolio["BTC-USD"]["exchange"], "RH")
        self.assertEqual(portfolio["BTC-USD"]["total_invested"], 0.0)
        
        # Try to add same coin again
        result2 = add_coin_interactive("BTC", "RH")
        self.assertFalse(result2)


if __name__ == '__main__':
    unittest.main()
