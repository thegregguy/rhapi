"""
Unit tests for trader.core module.
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal
import time

from trader.core import Trader
from trader.config import Config


class TestTraderCore(unittest.TestCase):
    """Tests for the Trader class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = Config()
        self.config.AUTO_DRY_RUN = True  # Always use dry-run in tests
        self.config.MAX_WORKERS = 1  # Sequential for predictable testing
        self.trader = Trader(self.config)
    
    def test_trader_initialization(self):
        """Test that trader initializes with config."""
        self.assertIsNotNone(self.trader)
        self.assertEqual(self.trader.config.AUTO_DRY_RUN, True)
    
    def test_calculate_profit_pct_with_total_invested(self):
        """Test profit calculation when total_invested is present."""
        symbol = "BTC-USD"
        state = {
            "total_invested": 100.0,
            "last_reference_price": 50000.0,
            "exchange": "RH"
        }
        current_val = Decimal("110.0")
        current_bid = Decimal("55000.0")
        
        profit_pct, mode, total_invested_used = self.trader.calculate_profit_pct(
            symbol, state, current_val, current_bid
        )
        
        # Should use total_invested, not current_val
        self.assertEqual(mode, "RISK_ON")
        self.assertAlmostEqual(profit_pct, 0.10, places=2)  # 10% profit
        self.assertEqual(total_invested_used, 100.0)
    
    def test_calculate_profit_pct_without_total_invested(self):
        """Test profit calculation when total_invested is missing but last_reference_price exists."""
        symbol = "BTC-USD"
        state = {
            "total_invested": 0.0,
            "last_reference_price": 50000.0,
            "exchange": "RH"
        }
        current_val = Decimal("110.0")
        current_bid = Decimal("55000.0")
        
        profit_pct, mode, total_invested_used = self.trader.calculate_profit_pct(
            symbol, state, current_val, current_bid
        )
        
        # Should use last_reference_price as fallback
        self.assertEqual(mode, "RISK_ON")
        self.assertAlmostEqual(profit_pct, 0.10, places=2)  # 10% based on reference
    
    def test_calculate_profit_pct_watch_mode(self):
        """Test profit calculation in WATCH mode (small position)."""
        symbol = "DOGE-USD"
        state = {
            "total_invested": 0.0,
            "last_reference_price": 0.08,
            "exchange": "RH"
        }
        current_val = Decimal("0.50")  # Small value, should be WATCH
        current_bid = Decimal("0.10")
        
        profit_pct, mode, total_invested_used = self.trader.calculate_profit_pct(
            symbol, state, current_val, current_bid
        )
        
        self.assertEqual(mode, "WATCH")
        self.assertAlmostEqual(profit_pct, 0.25, places=2)  # 25% increase from ref
    
    @patch('trader.core.get_unified_holdings')
    @patch('trader.core.get_unified_quote')
    @patch('trader.core.unified_place_order')
    def test_dry_run_no_orders_placed(self, mock_order, mock_quote, mock_holdings):
        """Test that no orders are placed in dry-run mode."""
        # Set up mocks
        mock_holdings.return_value = []
        mock_quote.return_value = {
            'ask': 50000.0,
            'bid': 49900.0,
            'exchange': 'RH'
        }
        
        # Create a state that would trigger a buy
        state = {
            "exchange": "RH",
            "total_invested": 0.0,
            "last_reference_price": 60000.0,  # Price has dropped
            "last_buy_time": 0,
            "can_buy": True,
            "profit_mult": 2.0,
            "dip_mult": 3.0
        }
        
        # Process coin in dry-run mode
        holdings_map = {}
        result = self.trader.process_coin("BTC-USD", state, holdings_map)
        
        # Verify no order was placed
        mock_order.assert_not_called()
        
        # Verify result mentions dry-run
        self.assertIsNotNone(result)
        self.assertIn("[DRY-RUN]", result)
    
    @patch('trader.core.get_unified_holdings')
    @patch('trader.core.get_unified_quote')
    @patch('trader.core.update_coin_state')
    def test_process_coin_updates_state(self, mock_update, mock_quote, mock_holdings):
        """Test that process_coin updates coin state."""
        mock_holdings.return_value = []
        mock_quote.return_value = {
            'ask': 50000.0,
            'bid': 49900.0,
            'exchange': 'RH'
        }
        
        state = {
            "exchange": "RH",
            "total_invested": 100.0,
            "last_reference_price": 50000.0,
            "last_buy_time": 0,
            "can_buy": False,
            "profit_mult": 2.0,
            "dip_mult": 3.0
        }
        
        holdings_map = {}
        result = self.trader.process_coin("BTC-USD", state, holdings_map)
        
        # Verify state was updated
        mock_update.assert_called_once()
        call_args = mock_update.call_args
        self.assertEqual(call_args[0][0], "BTC-USD")
        
        # Check that updates dict contains expected keys
        updates = call_args[0][1]
        self.assertIn("last_seen_price", updates)
        self.assertIn("last_profit_pct", updates)
        self.assertIn("current_value_usd", updates)
    
    @patch('trader.core.load_portfolio')
    @patch('trader.core.get_unified_holdings')
    def test_run_scan_empty_portfolio(self, mock_holdings, mock_load):
        """Test scan behavior with empty portfolio."""
        mock_load.return_value = {}
        mock_holdings.return_value = []
        
        # Should not raise exception
        self.trader.run_scan()
        
        # Holdings should not be called if portfolio is empty
        mock_holdings.assert_not_called()


class TestTraderConfig(unittest.TestCase):
    """Tests for the Config class."""
    
    @patch.dict('os.environ', {
        'AUTO_BUY_USD': '5.00',
        'AUTO_COOLDOWN': '300',
        'SCAN_INTERVAL': '30',
        'MAX_WORKERS': '8',
        'AUTO_DRY_RUN': 'true',
        'LOG_LEVEL': 'DEBUG'
    })
    def test_config_from_environment(self):
        """Test that config loads from environment variables."""
        config = Config()
        
        self.assertEqual(config.AUTO_BUY_USD, 5.00)
        self.assertEqual(config.AUTO_COOLDOWN, 300)
        self.assertEqual(config.SCAN_INTERVAL, 30)
        self.assertEqual(config.MAX_WORKERS, 8)
        self.assertEqual(config.AUTO_DRY_RUN, True)
        self.assertEqual(config.LOG_LEVEL, 'DEBUG')
    
    @patch.dict('os.environ', {}, clear=True)
    def test_config_defaults(self):
        """Test that config uses defaults when env vars not set."""
        # Clear dotenv cache
        from dotenv import load_dotenv
        load_dotenv()
        
        config = Config()
        
        self.assertEqual(config.AUTO_BUY_USD, 1.00)
        self.assertEqual(config.AUTO_COOLDOWN, 600)
        self.assertEqual(config.SCAN_INTERVAL, 15)
        self.assertEqual(config.MAX_WORKERS, 4)
        self.assertEqual(config.AUTO_DRY_RUN, False)
        self.assertEqual(config.LOG_LEVEL, 'INFO')


if __name__ == '__main__':
    unittest.main()
