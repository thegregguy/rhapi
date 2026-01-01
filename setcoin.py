import json
import os
import sys
import time
from typing import Dict, Any, Optional
from bot import get_unified_holdings, rh_client, cb_client
from bugeater import bug

PORTFOLIO_FILE = "portfolio.json"

DEFAULT_SETTINGS = {
    "can_buy": False,
    "profit_mult": 3.0,
    "dip_mult": 3.0,
    "last_buy_time": 0
}

# In-memory cache for portfolio to reduce disk I/O
_portfolio_cache: Optional[Dict[str, Any]] = None
_cache_timestamp: float = 0
_cache_ttl: float = 1.0  # Cache valid for 1 second


def _load_from_disk() -> Dict[str, Any]:
    """Load portfolio directly from disk."""
    if not os.path.exists(PORTFOLIO_FILE):
        return {}
    try:
        with open(PORTFOLIO_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        bug.error("Failed to load portfolio", e)
        return {}


def load_portfolio() -> Dict[str, Any]:
    """
    Load portfolio with caching support.
    
    Returns a cached version if recent enough, otherwise reloads from disk.
    """
    global _portfolio_cache, _cache_timestamp
    
    current_time = time.time()
    
    # Return cached version if still valid
    if _portfolio_cache is not None and (current_time - _cache_timestamp) < _cache_ttl:
        return _portfolio_cache.copy()
    
    # Load from disk and update cache
    bug.log(f"Loading {PORTFOLIO_FILE}...", label="IO")
    _portfolio_cache = _load_from_disk()
    _cache_timestamp = current_time
    
    return _portfolio_cache.copy()


def invalidate_cache() -> None:
    """Force cache invalidation."""
    global _portfolio_cache, _cache_timestamp
    _portfolio_cache = None
    _cache_timestamp = 0


def save_portfolio(data: Dict[str, Any]) -> None:
    """
    Save portfolio to disk atomically.
    
    Uses temp file and atomic rename to prevent corruption.
    """
    global _portfolio_cache, _cache_timestamp
    
    temp_file = PORTFOLIO_FILE + ".tmp"
    try:
        with open(temp_file, 'w') as f:
            json.dump(data, f, indent=4)
        os.replace(temp_file, PORTFOLIO_FILE)
        
        # Update cache
        _portfolio_cache = data.copy()
        _cache_timestamp = time.time()
        
        bug.success("Portfolio saved.")
    except Exception as e:
        bug.error("Failed to save portfolio", e)
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except:
                pass


def normalize_symbol(symbol: str, exchange: str) -> str:
    """
    Normalize symbol for the given exchange.
    
    Args:
        symbol: Symbol to normalize
        exchange: Target exchange ("RH" or "CB")
    
    Returns:
        Normalized symbol
    """
    # Remove suffixes in the correct order (USDC first, then USD)
    if symbol.endswith("-USDC"):
        base_symbol = symbol[:-5]  # Remove "-USDC"
    elif symbol.endswith("-USD"):
        base_symbol = symbol[:-4]  # Remove "-USD"
    else:
        base_symbol = symbol
    
    if exchange == "RH":
        return f"{base_symbol}-USD"
    elif exchange == "CB":
        return f"{base_symbol}-USDC"
    return symbol

def update_coin_state(symbol: str, new_data: Dict[str, Any]) -> None:
    """
    Update coin state in portfolio.
    
    Only writes to disk if data actually changed.
    
    Args:
        symbol: Trading symbol
        new_data: Dictionary of fields to update
    """
    portfolio = load_portfolio()
    symbol = symbol.upper()
    
    if symbol in portfolio:
        # Check if data actually changed
        changed = False
        for key, value in new_data.items():
            if portfolio[symbol].get(key) != value:
                changed = True
                break
        
        if changed:
            portfolio[symbol].update(new_data)
            save_portfolio(portfolio)
        else:
            bug.log(f"No changes for {symbol}, skipping disk write", label="IO")
    else:
        bug.warn(f"Attempted to update non-existent coin: {symbol}")

def add_coin_interactive(symbol: str, exchange: str) -> bool:
    """
    Add a new coin to the portfolio interactively.
    
    Args:
        symbol: Base symbol (e.g., "BTC")
        exchange: Exchange name ("RH" or "CB")
    
    Returns:
        True if added, False if already exists
    """
    symbol = normalize_symbol(symbol.upper(), exchange)
    portfolio = load_portfolio()
    
    if symbol not in portfolio:
        portfolio[symbol] = DEFAULT_SETTINGS.copy()
        portfolio[symbol]["exchange"] = exchange
        portfolio[symbol]["total_invested"] = 0.0
        portfolio[symbol]["last_reference_price"] = 0.0
        save_portfolio(portfolio)
        bug.success(f"Added {symbol}")
        return True
    return False

def audit_portfolio():
    """
    Scans both RH and CB and merges into portfolio.json
    """
    portfolio = load_portfolio()
    holdings = get_unified_holdings() 
    
    bug.section(f"Auditing {len(holdings)} Holdings")
    print(f"{'EXCH':<5} | {'SYMBOL':<10} | {'QTY':<10}")
    print("-" * 35)
    
    updated = 0

    for item in holdings:
        sym = item['symbol']
        qty = item['qty']
        exch = item['exchange']

        print(f"{exch:<5} | {sym:<10} | {qty:<10.6f}")
        
        # Add to portfolio if missing
        if sym not in portfolio:
            portfolio[sym] = DEFAULT_SETTINGS.copy()
            portfolio[sym]["exchange"] = exch
            portfolio[sym]["total_invested"] = 0.0 
            portfolio[sym]["last_reference_price"] = 0.0
            bug.log(f"New asset detected: {sym} ({exch})")
        
        # Ensure exchange tag is correct
        portfolio[sym]['exchange'] = exch
        updated += 1

    save_portfolio(portfolio)
    bug.success(f"Audit Complete. Synced {updated} assets.")

if __name__ == "__main__":
    bug.section("SETCOIN.py Debug Mode")
    bug.log("Testing Audit...")
    audit_portfolio()
