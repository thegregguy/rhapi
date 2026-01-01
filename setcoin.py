import json
import os
import sys
import threading
from bugeater import bug

PORTFOLIO_FILE = "portfolio.json"

# Thread lock for atomic file operations
_portfolio_lock = threading.Lock()

# Portfolio cache
_portfolio_cache = None
_cache_timestamp = 0
_cache_ttl = 5  # Cache TTL in seconds

DEFAULT_SETTINGS = {
    "can_buy": False,
    "profit_mult": 3.0,
    "dip_mult": 3.0,
    "last_buy_time": 0
}

def normalize_symbol(symbol: str, exchange: str) -> str:
    """Normalize symbol based on exchange"""
    symbol = symbol.upper()
    
    if exchange == "RH":
        if "-USDC" in symbol:
            symbol = symbol.replace("-USDC", "-USD")
        elif "-USD" not in symbol:
            symbol += "-USD"
    elif exchange == "CB":
        if "-USD" in symbol and "-USDC" not in symbol:
            symbol = symbol.replace("-USD", "-USDC")
        elif "-USDC" not in symbol:
            symbol += "-USDC"
    
    return symbol

def load_portfolio(use_cache=True):
    """Load portfolio with optional caching"""
    global _portfolio_cache, _cache_timestamp
    
    import time
    current_time = time.time()
    
    if use_cache and _portfolio_cache and (current_time - _cache_timestamp) < _cache_ttl:
        return _portfolio_cache.copy()
    
    bug.log(f"Loading {PORTFOLIO_FILE}...", label="IO")
    if not os.path.exists(PORTFOLIO_FILE): 
        return {}
    try:
        with open(PORTFOLIO_FILE, 'r') as f:
            data = json.load(f)
        _portfolio_cache = data.copy()
        _cache_timestamp = current_time
        return data
    except Exception as e: 
        bug.error("Failed to load portfolio", e)
        return {}

def _save_portfolio_unlocked(data):
    """Internal save portfolio function without locking (assumes lock is already held)"""
    global _portfolio_cache, _cache_timestamp
    
    temp_file = PORTFOLIO_FILE + ".tmp"
    try:
        with open(temp_file, 'w') as f:
            json.dump(data, f, indent=4)
        os.replace(temp_file, PORTFOLIO_FILE)
        
        # Update cache
        _portfolio_cache = data.copy()
        import time
        _cache_timestamp = time.time()
        
        bug.success("Portfolio saved.")
    except Exception as e:
        bug.error("Failed to save portfolio", e)
        if os.path.exists(temp_file):
            os.remove(temp_file)

def save_portfolio(data):
    """Save portfolio atomically with temporary file"""
    with _portfolio_lock:
        _save_portfolio_unlocked(data)

def update_coin_state(symbol, new_data):
    """Update coin state atomically"""
    with _portfolio_lock:
        portfolio = load_portfolio(use_cache=False)
        symbol = symbol.upper()
        if symbol in portfolio:
            portfolio[symbol].update(new_data)
            _save_portfolio_unlocked(portfolio)  # Use unlocked version since we already have the lock

def add_coin_interactive(symbol, exchange):
    """Add a coin to the portfolio interactively"""
    symbol = normalize_symbol(symbol, exchange)

    portfolio = load_portfolio(use_cache=False)
    
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
    Uses lazy import to avoid initialization at module level
    """
    # Lazy import to avoid initialization issues in tests
    from bot import get_unified_holdings
    
    portfolio = load_portfolio(use_cache=False)
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
