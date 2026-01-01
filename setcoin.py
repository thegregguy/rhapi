import json
import os
import sys
import threading
from bot import get_unified_holdings, rh_client, cb_client
from bugeater import bug

PORTFOLIO_FILE = "portfolio.json"

# Thread lock for safe concurrent portfolio updates
_portfolio_lock = threading.Lock()

DEFAULT_SETTINGS = {
    "can_buy": False,
    "profit_mult": 3.0,
    "dip_mult": 3.0,
    "last_buy_time": 0
}

def load_portfolio():
    bug.log(f"Loading {PORTFOLIO_FILE}...", label="IO")
    if not os.path.exists(PORTFOLIO_FILE): 
        return {}
    try:
        with open(PORTFOLIO_FILE, 'r') as f: return json.load(f)
    except Exception as e: 
        bug.error("Failed to load portfolio", e)
        return {}

def save_portfolio(data):
    # Thread-safe save with lock
    with _portfolio_lock:
        temp_file = PORTFOLIO_FILE + ".tmp"
        try:
            with open(temp_file, 'w') as f: json.dump(data, f, indent=4)
            os.replace(temp_file, PORTFOLIO_FILE)
            bug.success("Portfolio saved.")
        except Exception as e:
            bug.error("Failed to save portfolio", e)

def update_coin_state(symbol, new_data):
    # Thread-safe update with lock
    with _portfolio_lock:
        portfolio = load_portfolio()
        # Normalize keys just in case, but keep suffix
        symbol = symbol.upper()
        if symbol in portfolio:
            portfolio[symbol].update(new_data)
            # Save within the same lock to ensure atomicity
            temp_file = PORTFOLIO_FILE + ".tmp"
            try:
                with open(temp_file, 'w') as f: json.dump(portfolio, f, indent=4)
                os.replace(temp_file, PORTFOLIO_FILE)
            except Exception as e:
                bug.error("Failed to save portfolio", e)

def add_coin_interactive(symbol, exchange):
    symbol = symbol.upper()
    
    # Auto-suffix based on exchange
    if exchange == "RH":
        if "-USD" not in symbol: symbol += "-USD"
        if "-USDC" in symbol: symbol = symbol.replace("-USDC", "-USD")
    elif exchange == "CB":
        if "-USDC" not in symbol: symbol += "-USDC"
        if "-USD" in symbol and "-USDC" not in symbol: symbol = symbol.replace("-USD", "-USDC")

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
