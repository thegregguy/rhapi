#!/usr/bin/env python3
"""
Simplified CLI entrypoint for the modular trader.
"""
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
from bot import get_account_buying_power, rh_client, cb_client
from trader import Trader, Config


def clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def pause():
    """Pause and wait for user input."""
    try:
        input(f"\n{bug.BLUE}Press Enter to continue...{bug.ENDC}")
    except KeyboardInterrupt:
        pass


# ===========================
#       DIAGNOSTICS
# ===========================

def run_diagnostics():
    """Run system diagnostics to check API connections."""
    clear_screen()
    bug.section("🩺 SYSTEM DIAGNOSTICS 🩺")
    
    # 1. Environment Check
    bug.log("Checking Environment Variables...")
    if os.environ.get("API_KEY"):
        bug.success("RH API Key found.")
    else:
        bug.error("RH API Key MISSING.")
    
    if os.environ.get("CB_API_KEY"):
        bug.success("CB API Key found.")
    else:
        bug.error("CB API Key MISSING.")

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
        if rh_acct:
            bug.success(f"RH Connected. Buying Power: ${get_account_buying_power('RH'):.2f}")
        else:
            bug.error("RH Connection Failed (Empty Response)")
    except Exception as e:
        bug.error("RH Exception", e)

    bug.log("Testing Coinbase Connection...")
    try:
        cb_bal = get_account_buying_power('CB')
        bug.success(f"CB Connected. USDC Balance: ${cb_bal:.2f}")
    except Exception as e:
        bug.error("CB Exception", e)

    bug.section("Diagnostics Complete")
    pause()


# ===========================
#       TRADING LOGIC
# ===========================

def run_trading_loop():
    """Start the auto-trader using the new Trader class."""
    clear_screen()
    
    # Initialize trader with config from environment
    config = Config()
    trader = Trader(config)
    
    print(f"{bug.BLUE}Configuration: {config}{bug.ENDC}")
    print(f"{bug.BLUE}Press CTRL+C to stop and return to menu.{bug.ENDC}")
    
    if config.AUTO_DRY_RUN:
        print(f"{bug.WARNING}🔸 DRY-RUN MODE ENABLED 🔸{bug.ENDC}")
    
    pause()
    
    try:
        trader.run_loop()
    except KeyboardInterrupt:
        bug.log("\nStopping Trader... Returning to Menu.")
        time.sleep(1)


# ===========================
#   PORTFOLIO MANAGEMENT
# ===========================

def menu_manage_portfolio():
    """Interactive portfolio management menu."""
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
                print(f"{i:<3} | {d.get('exchange', '?'):<4} | {sym:<15} | "
                      f"{str(d.get('can_buy')):<5} | ${d.get('total_invested', 0):.2f}")
            
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


# ===========================
#       MAIN MENU
# ===========================

def main_menu():
    """Main interactive menu."""
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
                if os.path.exists("server_output.txt"):
                    os.remove("server_output.txt")
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
