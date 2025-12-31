import uuid
from decimal import Decimal, ROUND_DOWN
from rhapi import CryptoAPITrading
from cbapi import CoinbaseAPI
from bugeater import bug

# --- INITIALIZE API CLIENTS ---
bug.section("Initializing Bot Bridge")
rh_client = CryptoAPITrading()
cb_client = CoinbaseAPI()

# --- UNIFIED TRADING RULES ---
TRADING_RULES = {}

def load_trading_rules():
    global TRADING_RULES
    bug.log("Loading Unified Trading Rules...", label="BOT-INIT")
    try:
        res = rh_client.get_trading_pairs()
        results = res.get('results', []) if isinstance(res, dict) else res
        for item in results:
            sym = item.get('symbol')
            if sym:
                TRADING_RULES[sym] = {
                    "min_order": float(item.get('min_order_size', 0)),
                    "increment": item.get('asset_increment', '0.000001'),
                    "exchange": "RH"
                }
    except Exception as e:
        bug.error("Failed to load RH rules", e)

    if cb_client.client:
        bug.success("Coinbase Client Verified.")

try: load_trading_rules()
except: pass

# --- ROUTER FUNCTIONS ---

def get_router_exchange(symbol):
    """
    STRICT ROUTING:
    Ended in -USD  -> Robinhood
    Ended in -USDC -> Coinbase
    """
    if symbol.endswith("-USDC"): return "CB"
    if symbol.endswith("-USD"): return "RH"
    
    # Fallback/Default behavior if user forgets suffix
    if symbol in TRADING_RULES: return "RH"
    return "CB"

def get_unified_quote(symbol, exchange):
    """Returns a normalized dictionary regardless of exchange."""
    bug.log(f"Fetching Quote for {symbol} on {exchange}", label="ROUTER")
    
    if exchange == "RH":
        # RH always uses -USD
        if "-USDC" in symbol: 
            bug.warn(f"Attempted to check {symbol} on RH. Converting to -USD.")
            symbol = symbol.replace("-USDC", "-USD")
        elif "-USD" not in symbol: 
            symbol += "-USD"

        res = rh_client.get_best_bid_ask(symbol)
        if res and 'results' in res and len(res['results']) > 0:
            raw = res['results'][0]
            return {
                'ask': float(raw.get('ask_inclusive_of_buy_spread', 0)),
                'bid': float(raw.get('bid_inclusive_of_sell_spread', 0)),
                'exchange': 'RH'
            }
            
    elif exchange == "CB":
        # CB now strictly uses -USDC
        if "-USD" in symbol and "-USDC" not in symbol:
            bug.warn(f"Attempted to check {symbol} on CB. Converting to -USDC.")
            symbol = symbol.replace("-USD", "-USDC")
        elif "-USDC" not in symbol:
            symbol += "-USDC"

        price = cb_client.get_current_price(symbol)
        if price:
            return {
                'ask': price, 
                'bid': price, 
                'exchange': 'CB'
            }
            
    return None

def get_unified_holdings():
    """Returns a list of all assets from both exchanges."""
    all_holdings = []
    
    # 1. Robinhood (USD Pairs)
    try:
        res = rh_client.get_holdings()
        rh_data = res.get('results', []) if res and 'results' in res else []
        for h in rh_data:
            all_holdings.append({
                'symbol': h.get('asset_code') + "-USD",
                'qty': float(h.get('quantity_available_for_trading', 0)),
                'exchange': 'RH'
            })
    except Exception as e:
        bug.error("Failed to get RH holdings", e)

    # 2. Coinbase (USDC Pairs)
    try:
        if cb_client.client:
            response = cb_client.client.get_accounts()
            accts_list = getattr(response, 'accounts', []) if hasattr(response, 'accounts') else response.get('accounts', [])
            
            for acc in accts_list:
                curr = getattr(acc, 'currency', None) or (acc.get('currency') if hasattr(acc, 'get') else None)
                
                # Exclude standard fiat wallets
                if curr and curr not in ["USD", "USDC"]:
                    bal_obj = getattr(acc, 'available_balance', None) or (acc.get('available_balance') if hasattr(acc, 'get') else {})
                    val = getattr(bal_obj, 'value', 0) if hasattr(bal_obj, 'value') else bal_obj.get('value', 0)
                    
                    bal = float(val)
                    if bal > 0:
                        # !!! CRITICAL: COINBASE ASSETS ARE PAIRED WITH USDC !!!
                        all_holdings.append({
                            'symbol': f"{curr}-USDC",
                            'qty': bal,
                            'exchange': 'CB'
                        })
    except Exception as e:
        bug.error("Failed to get CB holdings", e)
    
    return all_holdings

def unified_place_order(symbol, side, quantity_or_dollars, exchange):
    bug.warn(f"ROUTING ORDER: {side.upper()} {symbol} ({quantity_or_dollars}) via {exchange}")
    
    if exchange == "RH":
        # Force USD
        clean_sym = symbol.replace("-USDC", "-USD") if "-USDC" in symbol else symbol
        if "-USD" not in clean_sym: clean_sym += "-USD"
        
        return rh_client.place_order(str(uuid.uuid4()), side, "market", clean_sym, {"asset_quantity": str(quantity_or_dollars)})
    
    elif exchange == "CB":
        # Force USDC
        clean_sym = symbol.replace("-USD", "-USDC") if "-USD" in symbol and "-USDC" not in symbol else symbol
        if "-USDC" not in clean_sym: clean_sym += "-USDC"
        
        if side == "buy":
            return cb_client.buy(clean_sym, float(quantity_or_dollars))
        elif side == "sell":
            return cb_client.sell(clean_sym)

def get_account_buying_power(exchange):
    if exchange == "RH":
        acct = rh_client.get_account()
        if acct: return float(acct.get('buying_power', 0))
    elif exchange == "CB":
        return cb_client.get_usdc_balance() # Changed to USDC
    return 0.0

def rh_smart_quantity(symbol, dollars, ask_price):
    if "-USD" not in symbol: symbol += "-USD"
    if ask_price == 0: return "0"
    raw_qty = dollars / ask_price
    rules = TRADING_RULES.get(symbol)
    if not rules: return "{:.6f}".format(raw_qty)
    if raw_qty < rules['min_order']: return "0"
    try:
        inc_str = str(rules['increment'])
        d_qty = Decimal(str(raw_qty))
        d_inc = Decimal(inc_str)
        valid_qty = d_qty.quantize(d_inc, rounding=ROUND_DOWN)
        precision = 0
        cleaned = inc_str.rstrip('0')
        if '.' in cleaned: precision = len(cleaned.split('.')[1])
        return f"{{:.{precision}f}}".format(valid_qty)
    except: return "{:.6f}".format(raw_qty)
