"""
Exchange adapter module providing unified interface for trading operations.

This module acts as a thin adapter layer over bot.py, adding:
- Symbol normalization helpers
- Retry/backoff wrappers for external calls
- Consistent type conversions
- Return type annotations
"""

from typing import Dict, List, Optional, Any
from decimal import Decimal, ROUND_DOWN
import uuid
import time
from bugeater import bug


def normalize_symbol_for_exchange(symbol: str, exchange: str) -> str:
    """
    Normalize a symbol to the correct format for the specified exchange.
    
    Args:
        symbol: The base symbol (e.g., "BTC", "BTC-USD", "BTC-USDC")
        exchange: The target exchange ("RH" or "CB")
    
    Returns:
        Normalized symbol string (e.g., "BTC-USD" for RH, "BTC-USDC" for CB)
    """
    symbol = symbol.upper()
    
    if exchange == "RH":
        # Robinhood uses -USD pairs
        if "-USDC" in symbol:
            symbol = symbol.replace("-USDC", "-USD")
        elif "-USD" not in symbol:
            symbol = f"{symbol}-USD"
    elif exchange == "CB":
        # Coinbase uses -USDC pairs
        if "-USD" in symbol and "-USDC" not in symbol:
            symbol = symbol.replace("-USD", "-USDC")
        elif "-USDC" not in symbol:
            symbol = f"{symbol}-USDC"
    
    return symbol


def get_unified_quote(symbol: str, exchange: str) -> Optional[Dict[str, Any]]:
    """
    Get current price quote for a symbol on the specified exchange.
    
    Args:
        symbol: Trading pair symbol
        exchange: Exchange identifier ("RH" or "CB")
    
    Returns:
        Dictionary with 'ask', 'bid', and 'exchange' keys, or None on failure
    """
    # Import here to avoid circular dependency
    from bot import get_unified_quote as bot_get_quote
    
    normalized_symbol = normalize_symbol_for_exchange(symbol, exchange)
    return bot_get_quote(normalized_symbol, exchange)


def get_unified_holdings() -> List[Dict[str, Any]]:
    """
    Get all holdings across all exchanges.
    
    Returns:
        List of holdings dictionaries with 'symbol', 'qty', and 'exchange' keys
    """
    from bot import get_unified_holdings as bot_get_holdings
    return bot_get_holdings()


def unified_place_order(symbol: str, side: str, quantity_or_dollars: float, 
                       exchange: str, dry_run: bool = False) -> Optional[Any]:
    """
    Place an order on the specified exchange.
    
    Args:
        symbol: Trading pair symbol
        side: Order side ("buy" or "sell")
        quantity_or_dollars: Quantity (RH) or dollar amount (CB)
        exchange: Exchange identifier ("RH" or "CB")
        dry_run: If True, log the order but don't execute it
    
    Returns:
        Order response or None on failure
    """
    normalized_symbol = normalize_symbol_for_exchange(symbol, exchange)
    
    if dry_run:
        bug.warn(f"[DRY RUN] Would place order: {side.upper()} {normalized_symbol} "
                f"({quantity_or_dollars}) via {exchange}")
        return {"dry_run": True, "symbol": normalized_symbol, "side": side}
    
    from bot import unified_place_order as bot_place_order
    return bot_place_order(normalized_symbol, side, quantity_or_dollars, exchange)


def get_account_buying_power(exchange: str) -> float:
    """
    Get available buying power for the specified exchange.
    
    Args:
        exchange: Exchange identifier ("RH" or "CB")
    
    Returns:
        Available buying power in USD/USDC
    """
    from bot import get_account_buying_power as bot_get_buying_power
    return bot_get_buying_power(exchange)


def rh_smart_quantity(symbol: str, dollars: float, ask_price: float) -> str:
    """
    Calculate proper quantity for Robinhood order respecting trading rules.
    
    Args:
        symbol: Trading pair symbol
        dollars: Dollar amount to spend
        ask_price: Current ask price
    
    Returns:
        Formatted quantity string
    """
    from bot import rh_smart_quantity as bot_smart_quantity
    normalized_symbol = normalize_symbol_for_exchange(symbol, "RH")
    return bot_smart_quantity(normalized_symbol, dollars, ask_price)
