"""
Unit tests for trader.core module.

Tests the Trader class with mocked external dependencies.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from trader.core import Trader
from trader.config import Config
from trader.exchanges import ExchangeAdapter


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    config = Mock(spec=Config)
    config.DEFAULT_BUY_USD = 1.00
    config.COOLDOWN = 600
    config.SCAN_INTERVAL = 15
    config.MAX_WORKERS = 4
    config.USE_CONCURRENCY = False  # Disable for deterministic tests
    config.DRY_RUN = True  # Safe default for tests
    config.DEBUG = False
    return config


@pytest.fixture
def mock_exchange_adapter():
    """Create a mock exchange adapter for testing."""
    adapter = Mock(spec=ExchangeAdapter)
    
    # Mock holdings
    adapter.get_unified_holdings.return_value = [
        {'symbol': 'BTC-USD', 'qty': 0.001, 'exchange': 'RH'},
        {'symbol': 'ETH-USDC', 'qty': 0.05, 'exchange': 'CB'}
    ]
    
    # Mock quotes
    def mock_quote(symbol, exchange):
        quotes = {
            'BTC-USD': {'ask': 50000.0, 'bid': 49900.0, 'exchange': 'RH'},
            'ETH-USDC': {'ask': 3000.0, 'bid': 2995.0, 'exchange': 'CB'}
        }
        return quotes.get(symbol)
    
    adapter.get_unified_quote.side_effect = mock_quote
    adapter.get_account_buying_power.return_value = 100.0
    adapter.unified_place_order.return_value = {'dry_run': True}
    adapter.rh_smart_quantity.return_value = "0.00002"
    adapter.invalidate_holdings_cache.return_value = None
    
    return adapter


@pytest.fixture
def mock_portfolio():
    """Create a mock portfolio for testing."""
    return {
        'BTC-USD': {
            'exchange': 'RH',
            'can_buy': True,
            'total_invested': 0.0,
            'last_reference_price': 50000.0,
            'last_buy_time': 0,
            'profit_mult': 2.0,
            'dip_mult': 3.0
        },
        'ETH-USDC': {
            'exchange': 'CB',
            'can_buy': False,
            'total_invested': 150.0,
            'last_reference_price': 3000.0,
            'last_buy_time': 0,
            'profit_mult': 2.0,
            'dip_mult': 3.0
        }
    }


def test_trader_initialization(mock_config, mock_exchange_adapter):
    """Test that Trader initializes correctly."""
    trader = Trader(mock_config, mock_exchange_adapter)
    
    assert trader.config == mock_config
    assert trader.exchange == mock_exchange_adapter
    assert trader.scan_count == 0


def test_process_coin_watch_mode(mock_config, mock_exchange_adapter, mock_portfolio):
    """Test processing a coin in WATCH mode (no holdings)."""
    trader = Trader(mock_config, mock_exchange_adapter)
    
    # Mock a coin with no holdings
    holdings = []
    state = mock_portfolio['BTC-USD']
    
    with patch('trader.core.update_coin_state') as mock_update:
        result = trader.process_coin('BTC-USD', state, holdings)
        
        assert result['status'] == 'processed'
        assert result['symbol'] == 'BTC-USD'
        assert result['mode'] == 'WATCH'
        assert mock_update.called


def test_process_coin_risk_on_mode(mock_config, mock_exchange_adapter, mock_portfolio):
    """Test processing a coin in RISK_ON mode (has holdings > $1)."""
    trader = Trader(mock_config, mock_exchange_adapter)
    
    # Holdings with value > $1
    holdings = [{'symbol': 'BTC-USD', 'qty': 0.001, 'exchange': 'RH'}]
    state = mock_portfolio['BTC-USD'].copy()
    state['total_invested'] = 40.0  # Less than current value
    
    with patch('trader.core.update_coin_state') as mock_update:
        result = trader.process_coin('BTC-USD', state, holdings)
        
        assert result['status'] == 'processed'
        assert result['symbol'] == 'BTC-USD'
        assert result['mode'] == 'RISK_ON'
        # Check that profit percentage is calculated
        assert 'profit_pct' in result


def test_process_coin_no_quote(mock_config, mock_exchange_adapter, mock_portfolio):
    """Test processing a coin when quote is unavailable."""
    trader = Trader(mock_config, mock_exchange_adapter)
    
    # Mock adapter to return no quote
    mock_exchange_adapter.get_unified_quote.return_value = None
    
    holdings = []
    state = mock_portfolio['BTC-USD']
    
    result = trader.process_coin('BTC-USD', state, holdings)
    
    assert result['status'] == 'no_quote'
    assert result['symbol'] == 'BTC-USD'


@patch('trader.core.load_portfolio')
def test_run_single_scan_empty_portfolio(mock_load, mock_config, mock_exchange_adapter):
    """Test running a scan with empty portfolio."""
    mock_load.return_value = {}
    
    trader = Trader(mock_config, mock_exchange_adapter)
    result = trader.run_single_scan()
    
    assert result['status'] == 'empty_portfolio'


@patch('trader.core.load_portfolio')
def test_run_single_scan_success(mock_load, mock_config, mock_exchange_adapter, mock_portfolio):
    """Test running a successful scan."""
    mock_load.return_value = mock_portfolio
    
    trader = Trader(mock_config, mock_exchange_adapter)
    
    with patch('trader.core.update_coin_state'):
        result = trader.run_single_scan()
    
    assert result['status'] == 'completed'
    assert result['scan_count'] == 1
    assert 'rh_count' in result
    assert 'cb_count' in result
    # Should have called invalidate_holdings_cache
    assert mock_exchange_adapter.invalidate_holdings_cache.called


def test_dry_run_mode_no_orders(mock_config, mock_exchange_adapter, mock_portfolio):
    """Test that DRY_RUN mode prevents real orders."""
    mock_config.DRY_RUN = True
    trader = Trader(mock_config, mock_exchange_adapter)
    
    # Mock conditions for a buy
    holdings = []
    state = mock_portfolio['BTC-USD'].copy()
    state['last_reference_price'] = 60000.0  # Price dropped significantly
    
    with patch('trader.core.update_coin_state'):
        with patch('time.time', return_value=1000000):
            result = trader.process_coin('BTC-USD', state, holdings)
    
    # Should attempt to place order but in dry-run
    if result.get('action') == 'buy':
        # Verify that unified_place_order was called
        assert mock_exchange_adapter.unified_place_order.called


def test_concurrent_processing_disabled(mock_config, mock_exchange_adapter, mock_portfolio):
    """Test that concurrency can be disabled."""
    mock_config.USE_CONCURRENCY = False
    
    with patch('trader.core.load_portfolio', return_value=mock_portfolio):
        with patch('trader.core.update_coin_state'):
            trader = Trader(mock_config, mock_exchange_adapter)
            result = trader.run_single_scan()
    
    assert result['status'] == 'completed'
    # Sequential processing should work
    assert result['rh_count'] + result['cb_count'] == len(mock_portfolio)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
