"""
Exchange API wrappers with normalization, retries, and type handling.
"""
import time
from decimal import Decimal
from typing import Dict, List, Optional, Union
from bugeater import bug


def normalize_symbol(symbol: str, exchange: str) -> str:
    """
    Normalize symbol to use correct suffix for the exchange.
    RH uses -USD, CB uses -USDC.
    
    Args:
        symbol: Base symbol (e.g., 'BTC' or 'BTC-USD' or 'BTC-USDC')
        exchange: 'RH' or 'CB'
    
    Returns:
        Normalized symbol with appropriate suffix
    """
    # Remove any existing suffixes (order matters: check longer suffix first)
    if symbol.endswith("-USDC"):
        base = symbol[:-5]  # Remove "-USDC"
    elif symbol.endswith("-USD"):
        base = symbol[:-4]  # Remove "-USD"
    else:
        base = symbol
    
    if exchange == "RH":
        return f"{base}-USD"
    elif exchange == "CB":
        return f"{base}-USDC"
    else:
        raise ValueError(f"Unknown exchange: {exchange}")


def retry_with_backoff(func, max_retries=3, initial_delay=1.0):
    """
    Retry a function with exponential backoff.
    
    Args:
        func: Function to retry (should be a lambda or callable)
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
    
    Returns:
        Function result or None on failure
    """
    delay = initial_delay
    for attempt in range(max_retries):
        try:
            result = func()
            return result
        except Exception as e:
            if attempt < max_retries - 1:
                bug.warn(f"Retry {attempt + 1}/{max_retries} after error: {e}")
                time.sleep(delay)
                delay *= 2  # Exponential backoff
            else:
                bug.error(f"Failed after {max_retries} attempts", e)
                return None


def get_unified_quote(symbol: str, exchange: str) -> Optional[Dict]:
    """
    Get normalized quote for a symbol.
    
    Args:
        symbol: Symbol to quote
        exchange: 'RH' or 'CB'
    
    Returns:
        Dict with 'ask', 'bid', 'exchange' or None on failure
    """
    # Import here to avoid circular dependency
    from bot import get_unified_quote as bot_get_quote
    
    normalized_symbol = normalize_symbol(symbol, exchange)
    
    def _fetch():
        return bot_get_quote(normalized_symbol, exchange)
    
    return retry_with_backoff(_fetch)


def get_unified_holdings() -> List[Dict]:
    """
    Get all holdings from both exchanges.
    
    Returns:
        List of dicts with 'symbol', 'qty', 'exchange'
    """
    from bot import get_unified_holdings as bot_get_holdings
    
    def _fetch():
        return bot_get_holdings()
    
    result = retry_with_backoff(_fetch)
    return result if result else []


def unified_place_order(symbol: str, side: str, quantity_or_dollars: Union[str, float, Decimal], 
                       exchange: str) -> Optional[Dict]:
    """
    Place an order with type normalization.
    
    Args:
        symbol: Trading symbol
        side: 'buy' or 'sell'
        quantity_or_dollars: Amount (normalized to float/str for API)
        exchange: 'RH' or 'CB'
    
    Returns:
        Order result or None on failure
    """
    from bot import unified_place_order as bot_place_order
    
    normalized_symbol = normalize_symbol(symbol, exchange)
    
    # Normalize quantity to string/float for API calls
    if isinstance(quantity_or_dollars, Decimal):
        quantity_or_dollars = float(quantity_or_dollars)
    
    def _place():
        return bot_place_order(normalized_symbol, side, quantity_or_dollars, exchange)
    
    return retry_with_backoff(_place)


def get_account_buying_power(exchange: str) -> float:
    """
    Get buying power for an exchange.
    
    Args:
        exchange: 'RH' or 'CB'
    
    Returns:
        Available buying power as float
    """
    from bot import get_account_buying_power as bot_get_power
    
    def _fetch():
        return bot_get_power(exchange)
    
    result = retry_with_backoff(_fetch)
    return result if result is not None else 0.0


def rh_smart_quantity(symbol: str, dollars: float, ask_price: float) -> str:
    """
    Calculate valid quantity for RH order respecting trading rules.
    
    Args:
        symbol: Trading symbol
        dollars: Dollar amount to spend
        ask_price: Current ask price
    
    Returns:
        Quantity as string formatted for RH API
    """
    from bot import rh_smart_quantity as bot_smart_qty
    
    normalized_symbol = normalize_symbol(symbol, "RH")
    return bot_smart_qty(normalized_symbol, dollars, ask_price)
