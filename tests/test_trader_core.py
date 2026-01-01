"""
Unit tests for the Trader core module.

Tests the main trading logic with mocked external dependencies.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal
import time

from trader.core import Trader
from trader.config import Config


@pytest.fixture
def mock_config():
    """Create a test configuration."""
    config = Config()
    config.default_buy_usd = Decimal("1.00")
    config.cooldown = 10  # Short cooldown for testing
    config.scan_interval = 1
    config.max_workers = 1  # Sequential for predictable tests
    config.auto_dry_run = True  # Default to dry run for safety
    return config


@pytest.fixture
def sample_portfolio():
    """Sample portfolio data."""
    return {
        "BTC-USD": {
            "exchange": "RH",
            "can_buy": True,
            "total_invested": 0.0,
            "last_reference_price": 50000.0,
            "last_buy_time": 0,
            "profit_mult": 2.0,
            "dip_mult": 3.0
        },
        "ETH-USDC": {
            "exchange": "CB",
            "can_buy": False,
            "total_invested": 10.0,
            "last_reference_price": 3000.0,
            "last_buy_time": 0,
            "profit_mult": 2.0,
            "dip_mult": 3.0
        }
    }


@pytest.fixture
def mock_holdings():
    """Sample holdings data."""
    return [
        {"symbol": "BTC-USD", "qty": 0.0001, "exchange": "RH"},
        {"symbol": "ETH-USDC", "qty": 0.005, "exchange": "CB"}
    ]


class TestTraderInit:
    """Test Trader initialization."""
    
    def test_init_with_config(self, mock_config):
        """Test trader initializes with provided config."""
        trader = Trader(mock_config)
        assert trader.config == mock_config
        assert trader.holdings_cache == []
    
    def test_init_without_config(self):
        """Test trader creates default config if none provided."""
        trader = Trader()
        assert trader.config is not None
        assert isinstance(trader.config, Config)


class TestHoldingsCache:
    """Test holdings caching logic."""
    
    @patch('trader.core.get_unified_holdings')
    def test_fetch_holdings_for_scan(self, mock_get_holdings, mock_config, mock_holdings):
        """Test holdings are fetched and cached."""
        mock_get_holdings.return_value = mock_holdings
        
        trader = Trader(mock_config)
        trader._fetch_holdings_for_scan()
        
        assert len(trader.holdings_cache) == 2
        assert trader.holdings_cache[0]["symbol"] == "BTC-USD"
        mock_get_holdings.assert_called_once()
    
    def test_get_coin_quantity(self, mock_config, mock_holdings):
        """Test getting quantity from cached holdings."""
        trader = Trader(mock_config)
        trader.holdings_cache = mock_holdings
        
        qty = trader._get_coin_quantity("BTC-USD", "RH")
        assert qty == 0.0001
        
        qty = trader._get_coin_quantity("ETH-USDC", "CB")
        assert qty == 0.005
        
        # Non-existent coin
        qty = trader._get_coin_quantity("DOGE-USD", "RH")
        assert qty == 0.0


class TestProcessCoin:
    """Test coin processing logic."""
    
    @patch('trader.core.update_coin_state')
    @patch('trader.core.get_unified_quote')
    def test_process_coin_no_quote(
        self, mock_quote, mock_update, mock_config, sample_portfolio
    ):
        """Test processing coin when quote fails."""
        mock_quote.return_value = None
        
        trader = Trader(mock_config)
        trader.holdings_cache = []
        
        # Should not raise exception
        trader.process_coin("BTC-USD", sample_portfolio["BTC-USD"])
        
        # Should not update state if no quote
        mock_update.assert_not_called()
    
    @patch('trader.core.update_coin_state')
    @patch('trader.core.unified_place_order')
    @patch('trader.core.get_unified_quote')
    @patch('trader.core.get_account_buying_power')
    def test_process_coin_buy_signal_dry_run(
        self, mock_buying_power, mock_quote, mock_order, mock_update,
        mock_config, sample_portfolio
    ):
        """Test buy signal in dry-run mode (should not place order)."""
        # Setup mocks
        mock_quote.return_value = {
            'ask': 45000.0,  # Price dropped from 50000
            'bid': 44900.0,
            'exchange': 'RH'
        }
        mock_buying_power.return_value = 100.0
        mock_order.return_value = None  # Dry run returns None
        
        trader = Trader(mock_config)
        trader.config.auto_dry_run = True
        trader.holdings_cache = [{"symbol": "BTC-USD", "qty": 0, "exchange": "RH"}]
        
        coin_state = sample_portfolio["BTC-USD"].copy()
        trader.process_coin("BTC-USD", coin_state)
        
        # Should call order with dry_run=True
        assert mock_order.called
        call_args = mock_order.call_args
        assert call_args[1]['dry_run'] is True
        
        # Should still update state
        assert mock_update.called
    
    @patch('trader.core.update_coin_state')
    @patch('trader.core.unified_place_order')
    @patch('trader.core.get_unified_quote')
    def test_process_coin_sell_signal(
        self, mock_quote, mock_order, mock_update,
        mock_config, sample_portfolio
    ):
        """Test sell signal when profit target hit."""
        # Setup: coin with profit
        mock_quote.return_value = {
            'ask': 3200.0,  # ETH up from 3000
            'bid': 3200.0,
            'exchange': 'CB'
        }
        mock_order.return_value = {"order_id": "test"}
        
        trader = Trader(mock_config)
        trader.config.auto_dry_run = True
        trader.holdings_cache = [{"symbol": "ETH-USDC", "qty": 0.005, "exchange": "CB"}]
        
        coin_state = sample_portfolio["ETH-USDC"].copy()
        coin_state["total_invested"] = 10.0  # RISK_ON mode
        
        trader.process_coin("ETH-USDC", coin_state)
        
        # Should attempt to sell
        assert mock_order.called
        call_args = mock_order.call_args
        assert call_args[0][1] == "sell"
    
    @patch('trader.core.update_coin_state')
    @patch('trader.core.get_unified_quote')
    def test_process_coin_watch_mode_updates_reference(
        self, mock_quote, mock_update, mock_config, sample_portfolio
    ):
        """Test that watch mode updates reference price when it's zero."""
        mock_quote.return_value = {
            'ask': 100.0,
            'bid': 100.0,
            'exchange': 'RH'
        }
        
        trader = Trader(mock_config)
        trader.holdings_cache = []
        
        coin_state = sample_portfolio["BTC-USD"].copy()
        coin_state["last_reference_price"] = 0.0  # No reference set
        coin_state["total_invested"] = 0.0
        
        trader.process_coin("BTC-USD", coin_state)
        
        # Should update state with reference price
        assert mock_update.called
        updates = mock_update.call_args[0][1]
        assert "last_reference_price" in updates
        assert updates["last_reference_price"] == 100.0


class TestRunLoop:
    """Test the main trading loop."""
    
    @patch('trader.core.load_portfolio')
    @patch('trader.core.get_unified_holdings')
    @patch('trader.core.get_unified_quote')
    @patch('trader.core.update_coin_state')
    def test_run_single_scan(
        self, mock_update, mock_quote, mock_holdings_func, mock_load,
        mock_config, sample_portfolio, mock_holdings
    ):
        """Test single scan execution."""
        mock_load.return_value = sample_portfolio
        mock_holdings_func.return_value = mock_holdings
        mock_quote.return_value = {'ask': 100.0, 'bid': 100.0, 'exchange': 'RH'}
        
        trader = Trader(mock_config)
        trader.run_single_scan()
        
        # Should fetch holdings once
        mock_holdings_func.assert_called_once()
        
        # Should process all coins
        assert mock_quote.call_count >= 2
    
    @patch('trader.core.load_portfolio')
    def test_run_single_scan_empty_portfolio(self, mock_load, mock_config):
        """Test scan with empty portfolio."""
        mock_load.return_value = {}
        
        trader = Trader(mock_config)
        # Should not raise exception
        trader.run_single_scan()


class TestDryRunMode:
    """Test that dry-run mode prevents real orders."""
    
    @patch('trader.core.unified_place_order')
    @patch('trader.core.get_unified_quote')
    @patch('trader.core.get_account_buying_power')
    @patch('trader.core.update_coin_state')
    def test_dry_run_prevents_buy_orders(
        self, mock_update, mock_buying_power, mock_quote, mock_order,
        mock_config, sample_portfolio
    ):
        """Test that dry-run mode passes dry_run=True to order function."""
        mock_quote.return_value = {'ask': 1.0, 'bid': 1.0, 'exchange': 'RH'}
        mock_buying_power.return_value = 100.0
        
        trader = Trader(mock_config)
        trader.config.auto_dry_run = True
        trader.holdings_cache = []
        
        # Trigger buy signal
        coin_state = sample_portfolio["BTC-USD"].copy()
        coin_state["last_reference_price"] = 100.0  # Current price way below
        
        trader.process_coin("BTC-USD", coin_state)
        
        # Check if order was called with dry_run=True
        if mock_order.called:
            call_kwargs = mock_order.call_args[1]
            assert 'dry_run' in call_kwargs
            assert call_kwargs['dry_run'] is True


class TestConcurrency:
    """Test concurrent processing."""
    
    @patch('trader.core.load_portfolio')
    @patch('trader.core.get_unified_holdings')
    @patch('trader.core.get_unified_quote')
    @patch('trader.core.update_coin_state')
    def test_concurrent_processing(
        self, mock_update, mock_quote, mock_holdings_func, mock_load,
        sample_portfolio, mock_holdings
    ):
        """Test that concurrent processing works."""
        config = Config()
        config.max_workers = 2  # Enable concurrency
        config.auto_dry_run = True
        
        mock_load.return_value = sample_portfolio
        mock_holdings_func.return_value = mock_holdings
        mock_quote.return_value = {'ask': 100.0, 'bid': 100.0, 'exchange': 'RH'}
        
        trader = Trader(config)
        trader.run_single_scan()
        
        # Should process all coins
        assert mock_quote.call_count >= 2
