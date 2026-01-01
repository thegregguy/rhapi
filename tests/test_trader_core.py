"""
Unit tests for the Trader core module.

Tests cover:
- Trader initialization
- Configuration handling
- Dry-run mode
- Holdings caching
- Concurrent processing
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal
from trader.core import Trader
from trader.config import Config


@pytest.fixture
def mock_config():
    """Create a test configuration."""
    config = Config()
    config.default_buy_usd = 1.0
    config.cooldown = 600
    config.scan_interval = 15
    config.max_workers = 2
    config.dry_run = True
    config.debug = False
    return config


@pytest.fixture
def mock_portfolio():
    """Create a mock portfolio."""
    return {
        "BTC-USD": {
            "exchange": "RH",
            "can_buy": True,
            "total_invested": 10.0,
            "last_reference_price": 50000.0,
            "last_buy_time": 0,
            "profit_mult": 2.0,
            "dip_mult": 3.0
        },
        "ETH-USDC": {
            "exchange": "CB",
            "can_buy": False,
            "total_invested": 5.0,
            "last_reference_price": 3000.0,
            "last_buy_time": 0,
            "profit_mult": 2.0,
            "dip_mult": 3.0
        }
    }


@pytest.fixture
def mock_holdings():
    """Create mock holdings data."""
    return [
        {"symbol": "BTC-USD", "qty": 0.001, "exchange": "RH"},
        {"symbol": "ETH-USDC", "qty": 0.002, "exchange": "CB"}
    ]


@pytest.fixture
def mock_quote():
    """Create a mock quote."""
    return {
        "ask": 50000.0,
        "bid": 49900.0,
        "exchange": "RH"
    }


class TestTraderInitialization:
    """Test Trader initialization and configuration."""
    
    def test_trader_init_with_config(self, mock_config):
        """Test trader initializes with provided config."""
        trader = Trader(mock_config)
        assert trader.config == mock_config
        assert trader.config.dry_run is True
        assert trader.running is False
    
    def test_trader_init_without_config(self):
        """Test trader creates default config when none provided."""
        trader = Trader()
        assert trader.config is not None
        assert isinstance(trader.config, Config)
        assert trader.running is False
    
    def test_holdings_cache_initialized_empty(self, mock_config):
        """Test holdings cache starts empty."""
        trader = Trader(mock_config)
        assert trader._holdings_cache == {}


class TestHoldingsFetch:
    """Test holdings fetching and caching."""
    
    @patch('trader.core.get_unified_holdings')
    def test_fetch_holdings_once(self, mock_get_holdings, mock_config, mock_holdings):
        """Test holdings are fetched and cached properly."""
        mock_get_holdings.return_value = mock_holdings
        
        trader = Trader(mock_config)
        cache = trader._fetch_holdings_once()
        
        # Verify holdings were fetched
        mock_get_holdings.assert_called_once()
        
        # Verify cache structure
        assert len(cache) == 2
        assert ("BTC-USD", "RH") in cache
        assert ("ETH-USDC", "CB") in cache
        assert cache[("BTC-USD", "RH")]["qty"] == 0.001
    
    @patch('trader.core.get_unified_holdings')
    def test_holdings_cache_updated_per_scan(self, mock_get_holdings, mock_config, mock_holdings):
        """Test holdings cache is updated on each scan."""
        mock_get_holdings.return_value = mock_holdings
        
        trader = Trader(mock_config)
        
        # First fetch
        cache1 = trader._fetch_holdings_once()
        
        # Modify mock data
        mock_holdings[0]["qty"] = 0.002
        
        # Second fetch
        cache2 = trader._fetch_holdings_once()
        
        # Verify two separate calls
        assert mock_get_holdings.call_count == 2


class TestDryRunMode:
    """Test dry-run mode prevents real orders."""
    
    @patch('trader.core.rh_smart_quantity')
    @patch('trader.core.unified_place_order')
    @patch('trader.core.get_unified_quote')
    @patch('trader.core.get_account_buying_power')
    @patch('trader.core.update_coin_state')
    def test_dry_run_prevents_buy_order(self, mock_update, mock_buying_power, 
                                        mock_quote, mock_place_order, mock_rh_quantity, mock_config):
        """Test dry-run mode prevents actual buy orders."""
        mock_config.dry_run = True
        mock_config.cooldown = 0  # No cooldown for test
        mock_config.default_buy_usd = 1.0
        
        # In WATCH mode with no holdings:
        # We need a small spread so target_dip = -0.05 (the floor)
        # cost_pct = (ask - bid) / ask = (50000 - 49500) / 50000 = 0.01 (1% spread)
        # target_dip = min((0.01 * 3) * -1, -0.05) = min(-0.03, -0.05) = -0.05
        # profit_pct = (current_bid - last_ref) / last_ref = (49500 - 50000) / 50000 = -0.01
        # Wait, we need profit_pct <= -0.05, so current_bid <= 47500
        # But ask/bid in the quote determines current price  
        # The quote bid will be used as current_bid
        # So I need to return a quote with TWO different bids? No, the quote is at current time
        # Let me re-read the code...
        # Actually, 'ask' and 'bid' in the quote are the CURRENT prices
        # So bid = 47500 means current_bid = 47500
        # cost_pct is calculated from the spread: (ask - bid) / ask
        # So ask=50000, bid=47500 => cost_pct = 0.05 => target_dip = min(-0.15, -0.05) = -0.15
        # And profit_pct = (47500 - 50000) / 50000 = -0.05
        # -0.05 is NOT <= -0.15
        # I need a TINY spread, so let's use ask=50000.00, bid=49999.50 (0.001% spread)
        # cost_pct = 0.00001, target_dip = -0.05 (floor)
        # Then I need current_bid to create profit_pct <= -0.05
        # But bid IS current_bid! So bid = 47500 => profit_pct = -0.05
        # Hmm, but then cost_pct = (50000 - 47500) / 50000 = 0.05... back to the same problem
        # 
        # The solution: use ask ≈ bid (tiny spread), and make BOTH low enough
        # ask = 47500, bid = 47499 => cost_pct ≈ 0.00002 => target_dip = -0.05
        # profit_pct = (47499 - 50000) / 50000 = -0.05
        # -0.05 <= -0.05 ✓
        mock_quote.return_value = {
            "ask": 47500.0,
            "bid": 47499.0,  # Tiny spread, both ~5% below reference
            "exchange": "RH"
        }
        mock_buying_power.return_value = 10.0
        mock_rh_quantity.return_value = "0.00002"  # Valid quantity
        mock_place_order.return_value = {"dry_run": True}
        
        trader = Trader(mock_config)
        trader._holdings_cache = {("BTC-USD", "RH"): {"qty": 0, "exchange": "RH"}}
        
        state = {
            "exchange": "RH",
            "can_buy": True,
            "total_invested": 0.0,
            "last_reference_price": 50000.0,  # Reference at 50k, current_bid will be 42500
            "last_buy_time": 0,
            "profit_mult": 2.0,
            "dip_mult": 3.0
        }
        
        trader.process_coin("BTC-USD", state)
        
        # Verify place_order was called with dry_run=True
        mock_place_order.assert_called()
        call_args = mock_place_order.call_args
        assert call_args.kwargs.get('dry_run') is True
    
    @patch('trader.core.unified_place_order')
    @patch('trader.core.get_unified_quote')
    @patch('trader.core.update_coin_state')
    def test_dry_run_prevents_sell_order(self, mock_update, mock_quote, 
                                        mock_place_order, mock_config):
        """Test dry-run mode prevents actual sell orders."""
        mock_config.dry_run = True
        
        mock_quote.return_value = {
            "ask": 60000.0,
            "bid": 60000.0,  # Big profit
            "exchange": "RH"
        }
        mock_place_order.return_value = {"dry_run": True}
        
        trader = Trader(mock_config)
        trader._holdings_cache = {("BTC-USD", "RH"): {"qty": 0.001, "exchange": "RH"}}
        
        state = {
            "exchange": "RH",
            "can_buy": True,
            "total_invested": 10.0,
            "last_reference_price": 50000.0,
            "last_buy_time": 0,
            "profit_mult": 1.5,  # Low multiplier to trigger sell
            "dip_mult": 3.0
        }
        
        trader.process_coin("BTC-USD", state)
        
        # Verify place_order was called with dry_run=True
        mock_place_order.assert_called()
        call_args = mock_place_order.call_args
        assert call_args.kwargs.get('dry_run') is True


class TestConcurrentProcessing:
    """Test concurrent coin processing."""
    
    @patch('trader.core.load_portfolio')
    @patch('trader.core.get_unified_holdings')
    @patch('trader.core.get_unified_quote')
    @patch('trader.core.update_coin_state')
    def test_concurrent_scan(self, mock_update, mock_quote, mock_holdings, 
                            mock_load, mock_config, mock_portfolio):
        """Test coins are processed concurrently when max_workers > 0."""
        mock_config.max_workers = 2
        mock_load.return_value = mock_portfolio
        mock_holdings.return_value = []
        mock_quote.return_value = {"ask": 50000.0, "bid": 49900.0, "exchange": "RH"}
        
        trader = Trader(mock_config)
        trader.run_scan()
        
        # Verify all coins were processed
        assert mock_quote.call_count >= 2
    
    @patch('trader.core.load_portfolio')
    @patch('trader.core.get_unified_holdings')
    @patch('trader.core.get_unified_quote')
    @patch('trader.core.update_coin_state')
    def test_sequential_scan(self, mock_update, mock_quote, mock_holdings,
                           mock_load, mock_config, mock_portfolio):
        """Test coins are processed sequentially when max_workers = 0."""
        mock_config.max_workers = 0
        mock_load.return_value = mock_portfolio
        mock_holdings.return_value = []
        mock_quote.return_value = {"ask": 50000.0, "bid": 49900.0, "exchange": "RH"}
        
        trader = Trader(mock_config)
        trader.run_scan()
        
        # Verify all coins were processed
        assert mock_quote.call_count >= 2


class TestProcessCoin:
    """Test individual coin processing logic."""
    
    @patch('trader.core.get_unified_quote')
    @patch('trader.core.update_coin_state')
    def test_process_coin_no_quote(self, mock_update, mock_quote, mock_config):
        """Test coin processing handles missing quote gracefully."""
        mock_quote.return_value = None
        
        trader = Trader(mock_config)
        trader._holdings_cache = {}
        
        state = {
            "exchange": "RH",
            "can_buy": True,
            "total_invested": 0.0,
            "last_reference_price": 0.0,
            "last_buy_time": 0,
            "profit_mult": 2.0,
            "dip_mult": 3.0
        }
        
        # Should not raise exception
        trader.process_coin("BTC-USD", state)
        
        # Verify no state update when no quote
        mock_update.assert_not_called()
    
    @patch('trader.core.get_unified_quote')
    @patch('trader.core.update_coin_state')
    def test_process_coin_updates_state(self, mock_update, mock_quote, mock_config):
        """Test coin processing updates state correctly."""
        mock_quote.return_value = {
            "ask": 50000.0,
            "bid": 49900.0,
            "exchange": "RH"
        }
        
        trader = Trader(mock_config)
        trader._holdings_cache = {}
        
        state = {
            "exchange": "RH",
            "can_buy": False,
            "total_invested": 0.0,
            "last_reference_price": 0.0,
            "last_buy_time": 0,
            "profit_mult": 2.0,
            "dip_mult": 3.0
        }
        
        trader.process_coin("BTC-USD", state)
        
        # Verify state was updated
        mock_update.assert_called_once()
        call_args = mock_update.call_args[0]
        updates = call_args[1]
        
        assert "last_seen_price" in updates
        assert updates["last_seen_price"] == 49900.0


class TestTraderLoop:
    """Test main trading loop functionality."""
    
    @patch('trader.core.load_portfolio')
    @patch('trader.core.get_unified_holdings')
    @patch('trader.core.time.sleep')
    def test_run_loop_stops_on_interrupt(self, mock_sleep, mock_holdings, 
                                        mock_load, mock_config):
        """Test trading loop stops on KeyboardInterrupt."""
        mock_load.return_value = {}
        mock_holdings.return_value = []
        mock_sleep.side_effect = KeyboardInterrupt()
        
        trader = Trader(mock_config)
        
        # Should not raise exception
        trader.run_loop()
        
        # Verify loop stopped
        assert trader.running is False
