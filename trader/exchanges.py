"""
Exchange adapter module providing unified interface to Robinhood and Coinbase.

This module wraps the underlying exchange APIs and provides:
- Symbol normalization
- Unified quote/holdings interfaces
- Order placement with retry logic
- Type conversions for API compatibility
"""

import uuid
import time
from decimal import Decimal, ROUND_DOWN
from typing import Dict, List, Optional, Any
from bugeater import bug

# Import the actual API clients
from rhapi import CryptoAPITrading
from cbapi import CoinbaseAPI

# Initialize clients (singleton pattern)
_rh_client: Optional[CryptoAPITrading] = None
_cb_client: Optional[CoinbaseAPI] = None


def get_rh_client() -> CryptoAPITrading:
    """Get or create Robinhood client."""
    global _rh_client
    if _rh_client is None:
        _rh_client = CryptoAPITrading()
    return _rh_client


def get_cb_client() -> CoinbaseAPI:
    """Get or create Coinbase client."""
    global _cb_client
    if _cb_client is None:
        _cb_client = CoinbaseAPI()
    return _cb_client


# Trading rules cache
TRADING_RULES: Dict[str, Dict[str, Any]] = {}


def load_trading_rules() -> None:
    """Load trading rules from Robinhood."""
    global TRADING_RULES
    bug.log("Loading trading rules...", label="EXCHANGES")
    try:
        rh = get_rh_client()
        res = rh.get_trading_pairs()
        results = res.get('results', []) if isinstance(res, dict) else res
        for item in results:
            sym = item.get('symbol')
            if sym:
                TRADING_RULES[sym] = {
                    "min_order": float(item.get('min_order_size', 0)),
                    "increment": item.get('asset_increment', '0.000001'),
                    "exchange": "RH"
                }
        bug.log(f"Loaded {len(TRADING_RULES)} trading rules")
    except Exception as e:
        bug.error("Failed to load trading rules", e)


# Load rules on module import
try:
    load_trading_rules()
except Exception:
    pass


def normalize_symbol_for_exchange(symbol: str, exchange: str) -> str:
    """
    Normalize symbol to the correct format for the given exchange.
    
    Args:
        symbol: The symbol to normalize (e.g., "BTC", "BTC-USD", "BTC-USDC")
        exchange: Target exchange ("RH" or "CB")
    
    Returns:
        Normalized symbol (e.g., "BTC-USD" for RH, "BTC-USDC" for CB)
    """
    # Remove existing suffixes
    base_symbol = symbol.replace("-USD", "").replace("-USDC", "")
    
    if exchange == "RH":
        return f"{base_symbol}-USD"
    elif exchange == "CB":
        return f"{base_symbol}-USDC"
    else:
        return symbol


def get_unified_quote(symbol: str, exchange: str) -> Optional[Dict[str, Any]]:
    """
    Get current price quote for a symbol on the specified exchange.
    
    Args:
        symbol: Trading symbol (will be normalized for exchange)
        exchange: "RH" or "CB"
    
    Returns:
        Dictionary with 'ask', 'bid', and 'exchange' keys, or None if error
    """
    normalized_symbol = normalize_symbol_for_exchange(symbol, exchange)
    bug.log(f"Fetching quote: {normalized_symbol} on {exchange}", label="QUOTE")
    
    try:
        if exchange == "RH":
            rh = get_rh_client()
            res = rh.get_best_bid_ask(normalized_symbol)
            if res and 'results' in res and len(res['results']) > 0:
                raw = res['results'][0]
                return {
                    'ask': float(raw.get('ask_inclusive_of_buy_spread', 0)),
                    'bid': float(raw.get('bid_inclusive_of_sell_spread', 0)),
                    'exchange': 'RH'
                }
        elif exchange == "CB":
            cb = get_cb_client()
            price = cb.get_current_price(normalized_symbol)
            if price:
                return {
                    'ask': price,
                    'bid': price,
                    'exchange': 'CB'
                }
    except Exception as e:
        bug.error(f"Failed to get quote for {normalized_symbol}", e)
    
    return None


def get_unified_holdings() -> List[Dict[str, Any]]:
    """
    Get all holdings from both exchanges.
    
    Returns:
        List of holdings, each with 'symbol', 'qty', and 'exchange' keys
    """
    all_holdings = []
    
    # Robinhood holdings
    try:
        rh = get_rh_client()
        res = rh.get_holdings()
        rh_data = res.get('results', []) if res and 'results' in res else []
        for h in rh_data:
            all_holdings.append({
                'symbol': h.get('asset_code') + "-USD",
                'qty': float(h.get('quantity_available_for_trading', 0)),
                'exchange': 'RH'
            })
    except Exception as e:
        bug.error("Failed to get RH holdings", e)
    
    # Coinbase holdings
    try:
        cb = get_cb_client()
        if cb.client:
            response = cb.client.get_accounts()
            accts_list = (
                getattr(response, 'accounts', [])
                if hasattr(response, 'accounts')
                else response.get('accounts', [])
            )
            
            for acc in accts_list:
                curr = (
                    getattr(acc, 'currency', None)
                    or (acc.get('currency') if hasattr(acc, 'get') else None)
                )
                
                # Exclude fiat wallets
                if curr and curr not in ["USD", "USDC"]:
                    bal_obj = (
                        getattr(acc, 'available_balance', None)
                        or (acc.get('available_balance') if hasattr(acc, 'get') else {})
                    )
                    val = (
                        getattr(bal_obj, 'value', 0)
                        if hasattr(bal_obj, 'value')
                        else bal_obj.get('value', 0)
                    )
                    
                    bal = float(val)
                    if bal > 0:
                        all_holdings.append({
                            'symbol': f"{curr}-USDC",
                            'qty': bal,
                            'exchange': 'CB'
                        })
    except Exception as e:
        bug.error("Failed to get CB holdings", e)
    
    return all_holdings


def unified_place_order(
    symbol: str,
    side: str,
    quantity_or_dollars: float,
    exchange: str,
    dry_run: bool = False
) -> Optional[Any]:
    """
    Place an order on the specified exchange.
    
    Args:
        symbol: Trading symbol (will be normalized)
        side: "buy" or "sell"
        quantity_or_dollars: For RH: quantity as string, For CB: dollar amount
        exchange: "RH" or "CB"
        dry_run: If True, log the order but don't execute
    
    Returns:
        Order response or None if error/dry-run
    """
    normalized_symbol = normalize_symbol_for_exchange(symbol, exchange)
    
    if dry_run:
        bug.warn(
            f"[DRY RUN] Would place order: {side.upper()} {normalized_symbol} "
            f"({quantity_or_dollars}) on {exchange}"
        )
        return None
    
    bug.warn(
        f"Placing order: {side.upper()} {normalized_symbol} "
        f"({quantity_or_dollars}) on {exchange}"
    )
    
    try:
        if exchange == "RH":
            rh = get_rh_client()
            return rh.place_order(
                str(uuid.uuid4()),
                side,
                "market",
                normalized_symbol,
                {"asset_quantity": str(quantity_or_dollars)}
            )
        elif exchange == "CB":
            cb = get_cb_client()
            if side == "buy":
                return cb.buy(normalized_symbol, float(quantity_or_dollars))
            elif side == "sell":
                return cb.sell(normalized_symbol)
    except Exception as e:
        bug.error(f"Order failed: {side} {normalized_symbol}", e)
    
    return None


def get_account_buying_power(exchange: str) -> float:
    """
    Get available buying power for the specified exchange.
    
    Args:
        exchange: "RH" or "CB"
    
    Returns:
        Available buying power in USD/USDC
    """
    try:
        if exchange == "RH":
            rh = get_rh_client()
            acct = rh.get_account()
            if acct:
                return float(acct.get('buying_power', 0))
        elif exchange == "CB":
            cb = get_cb_client()
            return cb.get_usdc_balance()
    except Exception as e:
        bug.error(f"Failed to get buying power for {exchange}", e)
    
    return 0.0


def rh_smart_quantity(symbol: str, dollars: float, ask_price: float) -> str:
    """
    Calculate valid quantity for Robinhood order based on trading rules.
    
    Args:
        symbol: Trading symbol
        dollars: Dollar amount to spend
        ask_price: Current ask price
    
    Returns:
        Formatted quantity string or "0" if invalid
    """
    normalized_symbol = normalize_symbol_for_exchange(symbol, "RH")
    
    if ask_price == 0:
        return "0"
    
    raw_qty = dollars / ask_price
    rules = TRADING_RULES.get(normalized_symbol)
    
    if not rules:
        return f"{raw_qty:.6f}"
    
    if raw_qty < rules['min_order']:
        return "0"
    
    try:
        inc_str = str(rules['increment'])
        d_qty = Decimal(str(raw_qty))
        d_inc = Decimal(inc_str)
        valid_qty = d_qty.quantize(d_inc, rounding=ROUND_DOWN)
        
        # Calculate precision
        precision = 0
        cleaned = inc_str.rstrip('0')
        if '.' in cleaned:
            precision = len(cleaned.split('.')[1])
        
        return f"{float(valid_qty):.{precision}f}"
    except Exception as e:
        bug.error(f"Quantity calculation error for {symbol}", e)
        return f"{raw_qty:.6f}"
