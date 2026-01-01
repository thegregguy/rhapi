import json
import os
import sys
from bot import get_unified_holdings, rh_client, cb_client
from bugeater import bug

PORTFOLIO_FILE = "portfolio.json"

DEFAULT_SETTINGS = {
    "can_buy": False,
    "profit_mult": 3.0,
    "dip_mult": 3.0,
    "last_buy_time": 0
}

# Cache for portfolio during a scan to avoid multiple file reads
_portfolio_cache = None


def normalize_symbol(symbol: str, exchange: str) -> str:
    """
    Normalize symbol to use correct suffix for the exchange.
    RH uses -USD, CB uses -USDC.
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

def load_portfolio(use_cache=False):
    """Load portfolio from file, optionally using cache."""
    global _portfolio_cache
    
    if use_cache and _portfolio_cache is not None:
        return _portfolio_cache
    
    bug.log(f"Loading {PORTFOLIO_FILE}...", label="IO")
    if not os.path.exists(PORTFOLIO_FILE): 
        return {}
    try:
        with open(PORTFOLIO_FILE, 'r') as f:
            portfolio = json.load(f)
            if use_cache:
                _portfolio_cache = portfolio
            return portfolio
    except Exception as e: 
        bug.error("Failed to load portfolio", e)
        return {}


def clear_portfolio_cache():
    """Clear the portfolio cache."""
    global _portfolio_cache
    _portfolio_cache = None

def save_portfolio(data, force=False):
    """
    Atomically save portfolio to disk.
    Only writes if force=True or data has changed.
    """
    global _portfolio_cache
    
    # Check if data has actually changed (unless forced)
    if not force:
        current = load_portfolio()
        if current == data:
            bug.log("Portfolio unchanged, skipping save.", label="IO")
            return
    
    temp_file = PORTFOLIO_FILE + ".tmp"
    try:
        with open(temp_file, 'w') as f:
            json.dump(data, f, indent=4)
        os.replace(temp_file, PORTFOLIO_FILE)
        _portfolio_cache = None  # Invalidate cache
        bug.success("Portfolio saved.")
    except Exception as e:
        bug.error("Failed to save portfolio", e)

def update_coin_state(symbol, new_data):
    portfolio = load_portfolio()
    # Normalize keys just in case, but keep suffix
    symbol = symbol.upper()
    if symbol in portfolio:
        portfolio[symbol].update(new_data)
        save_portfolio(portfolio)

def add_coin_interactive(symbol, exchange):
    symbol = symbol.upper()
    
    # Use normalize_symbol helper
    symbol = normalize_symbol(symbol, exchange)

    portfolio = load_portfolio()
    
    if symbol not in portfolio:
        portfolio[symbol] = DEFAULT_SETTINGS.copy()
        portfolio[symbol]["exchange"] = exchange
        portfolio[symbol]["total_invested"] = 0.0
        portfolio[symbol]["last_reference_price"] = 0.0
        save_portfolio(portfolio, force=True)
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
