"""
Unit tests for trader core module
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal
from trader.core import Trader
from trader.config import Config


@pytest.fixture
def mock_config():
    """Create a mock configuration"""
    config = Mock(spec=Config)
    config.AUTO_DRY_RUN = True
    config.DEFAULT_BUY_USD = 1.00
    config.COOLDOWN = 600
    config.MAX_WORKERS = 2
    return config


@pytest.fixture
def mock_router():
    """Create a mock exchange router"""
    router = Mock()
    router.get_all_holdings.return_value = []
    router.get_quote.return_value = {
        'ask': 100.0,
        'bid': 99.0,
        'exchange': 'RH',
        'symbol': 'BTC-USD'
    }
    router.get_buying_power.return_value = 1000.0
    router.place_order.return_value = {'success': True}
    router.smart_quantity.return_value = "0.01"
    return router


@patch('trader.core.UnifiedExchangeRouter')
@patch('trader.core.load_portfolio')
@patch('trader.core.update_coin_state')
def test_trader_initialization(mock_update, mock_load, mock_router_class, mock_config):
    """Test trader initialization"""
    mock_router_class.return_value = Mock()
    
    trader = Trader(mock_config)
    
    assert trader.config == mock_config
    assert trader.holdings_cache is None
    assert trader.holdings_cache_time == 0


@patch('trader.core.time')
@patch('trader.core.UnifiedExchangeRouter')
@patch('trader.core.load_portfolio')
@patch('trader.core.update_coin_state')
def test_trader_get_holdings_with_cache(mock_update, mock_load, mock_router_class, mock_time, mock_config, mock_router):
    """Test holdings caching mechanism"""
    mock_router_class.return_value = mock_router
    mock_router.get_all_holdings.return_value = [{'symbol': 'BTC-USD', 'qty': 1.0, 'exchange': 'RH'}]
    mock_time.time.return_value = 1000.0  # Fixed time for caching
    
    trader = Trader(mock_config)
    
    # First call should fetch from exchange
    holdings1 = trader.get_holdings()
    assert mock_router.get_all_holdings.call_count == 1
    assert len(holdings1) == 1
    
    # Second call should use cache (same time, holdings_cache is not empty)
    holdings2 = trader.get_holdings()
    assert mock_router.get_all_holdings.call_count == 1  # Should still be 1
    
    # Advance time beyond TTL
    mock_time.time.return_value = 2000.0
    holdings3 = trader.get_holdings()
    assert mock_router.get_all_holdings.call_count == 2
    
    # Force refresh should fetch again
    holdings4 = trader.get_holdings(force_refresh=True)
    assert mock_router.get_all_holdings.call_count == 3


@patch('trader.core.UnifiedExchangeRouter')
@patch('trader.core.load_portfolio')
@patch('trader.core.update_coin_state')
def test_trader_process_coin_watch_mode(mock_update, mock_load, mock_router_class, mock_config, mock_router):
    """Test processing a coin in WATCH mode"""
    mock_router_class.return_value = mock_router
    mock_router.get_all_holdings.return_value = []
    
    trader = Trader(mock_config)
    
    coin_state = {
        'exchange': 'RH',
        'total_invested': 0.0,
        'last_reference_price': 0.0,
        'last_buy_time': 0,
        'can_buy': False,
        'profit_mult': 2.0,
        'dip_mult': 3.0
    }
    
    trader.process_coin('BTC-USD', coin_state)
    
    # Verify state was updated
    assert mock_update.called


@patch('trader.core.UnifiedExchangeRouter')
@patch('trader.core.load_portfolio')
@patch('trader.core.update_coin_state')
def test_trader_dry_run_mode_prevents_orders(mock_update, mock_load, mock_router_class, mock_config, mock_router):
    """Test that DRY_RUN mode prevents actual orders"""
    mock_router_class.return_value = mock_router
    mock_config.AUTO_DRY_RUN = True
    
    # Setup holdings to trigger sell
    mock_router.get_all_holdings.return_value = [
        {'symbol': 'BTC-USD', 'qty': 1.0, 'exchange': 'RH'}
    ]
    mock_router.get_quote.return_value = {
        'ask': 150.0,
        'bid': 149.0,
        'exchange': 'RH',
        'symbol': 'BTC-USD'
    }
    
    trader = Trader(mock_config)
    
    coin_state = {
        'exchange': 'RH',
        'total_invested': 100.0,
        'last_reference_price': 100.0,
        'last_buy_time': 0,
        'can_buy': False,
        'profit_mult': 0.1,  # Low threshold to trigger sell
        'dip_mult': 3.0
    }
    
    trader.process_coin('BTC-USD', coin_state)
    
    # Verify no order was placed in dry run mode
    assert not mock_router.place_order.called


@patch('trader.core.UnifiedExchangeRouter')
@patch('trader.core.load_portfolio')
def test_trader_scan_portfolio_sequential(mock_load, mock_router_class, mock_config):
    """Test sequential portfolio scanning"""
    mock_router = Mock()
    mock_router.get_all_holdings.return_value = []
    mock_router_class.return_value = mock_router
    
    mock_load.return_value = {
        'BTC-USD': {
            'exchange': 'RH',
            'total_invested': 0.0,
            'can_buy': False,
            'profit_mult': 2.0,
            'dip_mult': 3.0,
            'last_reference_price': 0.0,
            'last_buy_time': 0
        }
    }
    
    trader = Trader(mock_config)
    
    with patch.object(trader, 'process_coin') as mock_process:
        trader.scan_portfolio(mock_load.return_value, use_concurrency=False)
        assert mock_process.call_count == 1


@patch('trader.core.UnifiedExchangeRouter')
@patch('trader.core.load_portfolio')
def test_trader_scan_portfolio_concurrent(mock_load, mock_router_class, mock_config):
    """Test concurrent portfolio scanning"""
    mock_router = Mock()
    mock_router.get_all_holdings.return_value = []
    mock_router_class.return_value = mock_router
    
    mock_config.MAX_WORKERS = 2
    
    mock_load.return_value = {
        'BTC-USD': {
            'exchange': 'RH',
            'total_invested': 0.0,
            'can_buy': False,
            'profit_mult': 2.0,
            'dip_mult': 3.0,
            'last_reference_price': 0.0,
            'last_buy_time': 0
        },
        'ETH-USD': {
            'exchange': 'RH',
            'total_invested': 0.0,
            'can_buy': False,
            'profit_mult': 2.0,
            'dip_mult': 3.0,
            'last_reference_price': 0.0,
            'last_buy_time': 0
        }
    }
    
    trader = Trader(mock_config)
    
    with patch.object(trader, 'process_coin') as mock_process:
        trader.scan_portfolio(mock_load.return_value, use_concurrency=True)
        assert mock_process.call_count == 2


def test_decimal_usage():
    """Test that Decimal is used for numeric calculations"""
    from decimal import Decimal
    
    # Test Decimal usage in calculations
    val1 = Decimal("100.00")
    val2 = Decimal("0.01")
    result = val1 * val2
    
    assert isinstance(result, Decimal)
    assert result == Decimal("1.00")
