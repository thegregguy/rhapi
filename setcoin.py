import json
import os
import sys
import hashlib
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

# In-memory cache for portfolio to reduce disk reads
_portfolio_cache: Optional[Dict[str, Any]] = None
_portfolio_hash: Optional[str] = None

def _hash_portfolio(data: Dict[str, Any]) -> str:
    """
    Generate a hash of the portfolio data for change detection.
    
    Args:
        data: Portfolio dictionary
    
    Returns:
        MD5 hash of the serialized portfolio
    """
    serialized = json.dumps(data, sort_keys=True)
    return hashlib.md5(serialized.encode()).hexdigest()


def normalize_symbol(symbol: str, exchange: str) -> str:
    """
    Normalize symbol format for the given exchange.
    
    Args:
        symbol: Base symbol (e.g., "BTC", "BTC-USD")
        exchange: Target exchange ("RH" or "CB")
    
    Returns:
        Normalized symbol string
    """
    symbol = symbol.upper()
    
    if exchange == "RH":
        if "-USDC" in symbol:
            symbol = symbol.replace("-USDC", "-USD")
        elif "-USD" not in symbol:
            symbol = f"{symbol}-USD"
    elif exchange == "CB":
        if "-USD" in symbol and "-USDC" not in symbol:
            symbol = symbol.replace("-USD", "-USDC")
        elif "-USDC" not in symbol:
            symbol = f"{symbol}-USDC"
    
    return symbol


def load_portfolio():
    """
    Load portfolio from disk with caching.
    
    Returns:
        Portfolio dictionary
    """
    global _portfolio_cache, _portfolio_hash
    
    bug.log(f"Loading {PORTFOLIO_FILE}...", label="IO")
    if not os.path.exists(PORTFOLIO_FILE):
        _portfolio_cache = {}
        _portfolio_hash = _hash_portfolio({})
        return {}
    
    try:
        with open(PORTFOLIO_FILE, 'r') as f:
            data = json.load(f)
            new_hash = _hash_portfolio(data)
            
            # Update cache
            _portfolio_cache = data
            _portfolio_hash = new_hash
            
            return data
    except Exception as e:
        bug.error("Failed to load portfolio", e)
        return {}


def get_portfolio() -> Dict[str, Any]:
    """
    Get cached portfolio or load from disk.
    
    Returns:
        Portfolio dictionary
    """
    global _portfolio_cache
    
    if _portfolio_cache is not None:
        return _portfolio_cache.copy()
    
    return load_portfolio()

def save_portfolio(data):
    """
    Save portfolio to disk atomically, only if changed.
    
    Args:
        data: Portfolio dictionary to save
    """
    global _portfolio_cache, _portfolio_hash
    
    new_hash = _hash_portfolio(data)
    
    # Skip save if data hasn't changed
    if _portfolio_hash == new_hash:
        bug.log("Portfolio unchanged, skipping save", label="IO")
        return
    
    temp_file = PORTFOLIO_FILE + ".tmp"
    try:
        with open(temp_file, 'w') as f:
            json.dump(data, f, indent=4)
        os.replace(temp_file, PORTFOLIO_FILE)
        
        # Update cache
        _portfolio_cache = data.copy()
        _portfolio_hash = new_hash
        
        bug.success("Portfolio saved.")
    except Exception as e:
        bug.error("Failed to save portfolio", e)

def update_coin_state(symbol, new_data):
    """
    Update state for a specific coin in the portfolio.
    
    Args:
        symbol: Coin symbol
        new_data: Dictionary of updates to apply
    """
    portfolio = load_portfolio()
    # Normalize keys just in case, but keep suffix
    symbol = symbol.upper()
    if symbol in portfolio:
        # Check if data actually changed before updating
        changed = False
        for key, value in new_data.items():
            if portfolio[symbol].get(key) != value:
                changed = True
                break
        
        if changed:
            portfolio[symbol].update(new_data)
            save_portfolio(portfolio)
        else:
            bug.log(f"No changes detected for {symbol}, skipping save", label="IO")

def add_coin_interactive(symbol, exchange):
    """
    Add a new coin to the portfolio interactively.
    
    Args:
        symbol: Coin symbol
        exchange: Exchange identifier ("RH" or "CB")
    
    Returns:
        True if coin was added, False if it already exists
    """
    symbol = normalize_symbol(symbol, exchange)
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
