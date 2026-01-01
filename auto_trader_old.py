import time
import os
import sys
from bugeater import bug
from setcoin import (
    load_portfolio, 
    update_coin_state, 
    audit_portfolio, 
    add_coin_interactive, 
    save_portfolio,
    PORTFOLIO_FILE
)
from bot import (
    get_unified_quote, 
    get_account_buying_power, 
    unified_place_order, 
    get_unified_holdings,
    rh_smart_quantity,
    rh_client,
    cb_client
)

# --- CONFIG ---
DEFAULT_BUY_USD = 1.00 
COOLDOWN = 600

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def pause():
    try:
        input(f"\n{bug.BLUE}Press Enter to continue...{bug.ENDC}")
    except KeyboardInterrupt:
        pass

# ===========================
#       DIAGNOSTICS
# ===========================

def run_diagnostics():
    clear_screen()
    bug.section("🩺 SYSTEM DIAGNOSTICS 🩺")
    
    # 1. Environment Check
    bug.log("Checking Environment Variables...")
    if os.environ.get("API_KEY"): bug.success("RH API Key found.")
    else: bug.error("RH API Key MISSING.")
    
    if os.environ.get("CB_API_KEY"): bug.success("CB API Key found.")
    else: bug.error("CB API Key MISSING.")

    # 2. File System Check
    bug.log("Checking File System...")
    if os.access(PORTFOLIO_FILE, os.R_OK): 
        bug.success(f"Portfolio file accessible: {PORTFOLIO_FILE}")
    else: 
        bug.warn(f"Portfolio file missing or not readable: {PORTFOLIO_FILE}")

    # 3. API Connectivity
    bug.log("Testing Robinhood Connection...")
    try:
        rh_acct = rh_client.get_account()
        if rh_acct: bug.success(f"RH Connected. Buying Power: ${get_account_buying_power('RH'):.2f}")
        else: bug.error("RH Connection Failed (Empty Response)")
    except Exception as e: bug.error("RH Exception", e)

    bug.log("Testing Coinbase Connection...")
    try:
        # Check USDC specific balance now
        cb_bal = get_account_buying_power('CB')
        bug.success(f"CB Connected. USDC Balance: ${cb_bal:.2f}")
    except Exception as e: bug.error("CB Exception", e)

    bug.section("Diagnostics Complete")
    pause()

# ===========================
#       TRADING LOGIC
# ===========================

def process_coin(symbol, state):
    exchange = state.get("exchange", "RH")
    
    # 1. Load Settings
    total_invested = state.get("total_invested", 0.0)
    last_ref = state.get("last_reference_price", 0.0)
    last_buy_ts = state.get("last_buy_time", 0)
    can_buy = state.get("can_buy", False)
    profit_mult = state.get("profit_mult", 2.0)
    dip_mult = state.get("dip_mult", 3.0)

    # 2. Get Live Holdings 
    holdings = get_unified_holdings()
    qty_avail = 0.0
    for h in holdings:
        # STRICT MATCHING (symbol includes suffix now)
        if h['symbol'] == symbol and h['exchange'] == exchange:
            qty_avail = h['qty']
            break

    # 3. Get Price
    quote = get_unified_quote(symbol, exchange)
    if not quote: 
        bug.warn(f"No quote for {symbol}")
        return

    ask = quote['ask']
    current_bid = quote['bid']

    # 4. Calculate Indicators
    # Simple Logic: If no spread info (CB), assume 1% cost basis
    cost_pct = 0.01 
    if exchange == "RH" and ask > 0:
         cost_pct = (ask - current_bid) / ask
         if cost_pct < 0.01: cost_pct = 0.01

    target_profit = max(cost_pct * profit_mult, 0.01)
    target_dip = min((cost_pct * dip_mult) * -1, -0.05)

    current_val = qty_avail * current_bid
    
    # Mode Determination
    mode = "WATCH"
    profit_pct = 0.0

    if current_val > 1.00: 
        mode = "RISK_ON"
        if total_invested <= 0: total_invested = current_val 
        profit_pct = (current_val - total_invested) / total_invested
    else:
        if last_ref == 0: last_ref = current_bid
        profit_pct = (current_bid - last_ref) / last_ref

    # 5. UI Output
    status_icon = "🟢" if can_buy else "👀"
    print(f"{status_icon} {symbol:<12} [{exchange}] | {mode:<8} | P/L: {profit_pct*100:6.2f}% | Price: ${current_bid:.4f}")
    
    # 6. Update State
    updates = {
        "last_seen_price": current_bid,
        "last_profit_pct": profit_pct,
        "current_value_usd": current_val
    }
    if mode == "WATCH" and last_ref == 0: updates["last_reference_price"] = current_bid
    update_coin_state(symbol, updates)

    # 7. EXECUTION
    
    # --- SELL ---
    if mode == "RISK_ON" and profit_pct >= target_profit:
        bug.success(f"🚀 {symbol} HIT TARGET ({profit_pct*100:.2f}%)! Selling...")
        
        res = unified_place_order(symbol, "sell", qty_avail, exchange)
        
        if res:
            bug.success("✅ Sell Order Placed.")
            update_coin_state(symbol, {"total_invested": 0.0, "last_reference_price": current_bid})
            time.sleep(2)

    # --- BUY ---
    elif can_buy and profit_pct <= target_dip:
        if (time.time() - last_buy_ts) > COOLDOWN:
            buying_power = get_account_buying_power(exchange)
            
            if buying_power >= DEFAULT_BUY_USD:
                bug.warn(f"📉 {symbol} DIP DETECTED ({profit_pct*100:.2f}%)! Buying...")
                
                amount_to_send = DEFAULT_BUY_USD
                # If RH, convert USD to Qty String
                if exchange == "RH":
                    amount_to_send = rh_smart_quantity(symbol, DEFAULT_BUY_USD, ask)
                    if float(amount_to_send) == 0: return

                res = unified_place_order(symbol, "buy", amount_to_send, exchange)
                
                if res:
                    bug.success(f"✅ Bought {symbol}!")
                    update_coin_state(symbol, {
                        "total_invested": total_invested + DEFAULT_BUY_USD,
                        "last_buy_time": time.time(),
                    })
                    time.sleep(2)
            else:
                bug.error(f"Not enough funds on {exchange} to buy {symbol}")

# ===========================
#       INTERACTIVE MENU
# ===========================

def run_trading_loop():
    clear_screen()
    bug.section("Starting Dual-Exchange Auto Trader")
    print(f"{bug.BLUE}Press CTRL+C to stop and return to menu.{bug.ENDC}")
    
    try:
        while True:
            portfolio = load_portfolio()
            if not portfolio:
                bug.warn("Portfolio empty. Please add coins first.")
                pause()
                break
            
            print(f"\n--- SCAN: {time.strftime('%H:%M:%S')} ---")
            
            rh_count = 0
            cb_count = 0
            
            for symbol, data in portfolio.items():
                try:
                    process_coin(symbol, data)
                    if data.get('exchange') == 'RH': rh_count += 1
                    else: cb_count += 1
                except KeyboardInterrupt:
                    raise 
                except Exception as e:
                    bug.error(f"Error processing {symbol}", e)
            
            print(f"--- Checked: {rh_count} RH | {cb_count} CB ---")
            print("Sleeping...")
            time.sleep(15)
            
    except KeyboardInterrupt:
        bug.log("\nStopping Trader... Returning to Menu.")
        time.sleep(1)

def menu_manage_portfolio():
    while True:
        try:
            clear_screen()
            bug.section("Portfolio Management")
            port = load_portfolio()
            
            print(f"{'IDX':<3} | {'EXCH':<4} | {'SYMBOL':<15} | {'BUY?':<5} | {'INVESTED'}")
            print("-" * 55)
            
            keys = list(port.keys())
            for i, sym in enumerate(keys):
                d = port[sym]
                print(f"{i:<3} | {d.get('exchange', '?'):<4} | {sym:<15} | {str(d.get('can_buy')):<5} | ${d.get('total_invested', 0):.2f}")
            
            print("\nOptions:")
            print("1. Toggle CAN_BUY for a coin")
            print("2. Add new Watch/Trade pair")
            print("3. Audit/Sync with Online Accounts")
            print("0. Back")
            
            ch = input("\nSelect > ")
            
            if ch == "1":
                idx = input("Enter IDX to toggle: ")
                if idx.isdigit() and int(idx) < len(keys):
                    sym = keys[int(idx)]
                    curr = port[sym].get('can_buy', False)
                    update_coin_state(sym, {'can_buy': not curr})
                    print(f"Toggled {sym} to {not curr}")
                    time.sleep(1)
            
            elif ch == "2":
                sym = input("Enter Symbol (e.g. BTC, DOGE): ").upper()
                exch = input("Exchange (RH or CB): ").upper()
                if exch not in ["RH", "CB"]: 
                    print("Invalid Exchange")
                else:
                    if add_coin_interactive(sym, exch):
                        print(f"Added {sym} to {exch} watch list.")
                    else:
                        print("Symbol already exists.")
                time.sleep(1)

            elif ch == "3":
                audit_portfolio()
                pause()

            elif ch == "0":
                break
        except KeyboardInterrupt:
            break

def main_menu():
    while True:
        try:
            clear_screen()
            print("=========================================")
            print("   🤖 UNIFIED CRYPTO BOT (RH + CB) 🤖")
            print("=========================================")
            if bug.enabled:
                print(f"{bug.HEADER}   🐛 DEBUG MODE ACTIVE 🐛{bug.ENDC}")
                print("=========================================")
            
            print("1. 🚀 Start Auto-Trader")
            print("2. ⚙️  Manage Portfolio / Watches")
            print("3. 🔍 Check Account Balances")
            print("4. 🧹 Clear Logs")
            print("9. 🩺 System Diagnostics")
            print("0. ❌ Exit")
            
            choice = input("\nSelect > ")
            
            if choice == "1":
                run_trading_loop()
            elif choice == "2":
                menu_manage_portfolio()
            elif choice == "3":
                bug.section("Balances")
                print(f"Robinhood USD : ${get_account_buying_power('RH'):.2f}")
                print(f"Coinbase USDC : ${get_account_buying_power('CB'):.2f}")
                pause()
            elif choice == "4":
                if os.path.exists("server_output.txt"): os.remove("server_output.txt")
                print("Logs cleared.")
                time.sleep(1)
            elif choice == "9":
                run_diagnostics()
            elif choice == "0":
                sys.exit()
        except KeyboardInterrupt:
            print("\nExiting...")
            sys.exit()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        bug.section("AutoTrader Self-Test")
        bug.log("Modules loaded successfully.")
        sys.exit(0)
        
    main_menu()
