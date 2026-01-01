"""
Core Trader implementation with scan loop, concurrency, and dry-run support.

This module contains the main Trader class that orchestrates the trading logic.
"""

import time
from typing import Dict, Any, Optional
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor, as_completed
from bugeater import bug
from trader.config import Config
from trader.exchanges import (
    get_unified_quote,
    get_unified_holdings,
    unified_place_order,
    get_account_buying_power,
    rh_smart_quantity,
    normalize_symbol_for_exchange
)
from setcoin import load_portfolio, update_coin_state


class Trader:
    """
    Main trading bot implementation.
    
    Orchestrates the trading loop with support for:
    - Concurrent coin processing
    - Single holdings fetch per scan
    - Dry-run mode
    - Configurable parameters
    """
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize the Trader.
        
        Args:
            config: Configuration object (creates default if None)
        """
        self.config = config or Config()
        self.running = False
        
        # Cache for holdings (refreshed each scan)
        self._holdings_cache: Dict[str, Dict[str, Any]] = {}
        
        bug.log(f"Trader initialized with config: {self.config}")
    
    def _fetch_holdings_once(self) -> Dict[str, Dict[str, Any]]:
        """
        Fetch all holdings once and cache by (symbol, exchange) key.
        
        Returns:
            Dictionary mapping (symbol, exchange) to holding info
        """
        holdings_list = get_unified_holdings()
        holdings_cache = {}
        
        for holding in holdings_list:
            key = (holding['symbol'], holding['exchange'])
            holdings_cache[key] = holding
        
        bug.log(f"Fetched {len(holdings_cache)} holdings", label="TRADER")
        return holdings_cache
    
    def process_coin(self, symbol: str, state: Dict[str, Any]) -> None:
        """
        Process a single coin's trading logic.
        
        Args:
            symbol: The coin symbol to process
            state: Current state data for the coin
        """
        exchange = state.get("exchange", "RH")
        
        # 1. Load Settings
        total_invested = state.get("total_invested", 0.0)
        last_ref = state.get("last_reference_price", 0.0)
        last_buy_ts = state.get("last_buy_time", 0)
        can_buy = state.get("can_buy", False)
        profit_mult = state.get("profit_mult", 2.0)
        dip_mult = state.get("dip_mult", 3.0)
        
        # 2. Get Live Holdings from cache
        cache_key = (symbol, exchange)
        qty_avail = 0.0
        if cache_key in self._holdings_cache:
            qty_avail = self._holdings_cache[cache_key]['qty']
        
        # 3. Get Price
        quote = get_unified_quote(symbol, exchange)
        if not quote:
            bug.warn(f"No quote for {symbol}")
            return
        
        ask = quote['ask']
        current_bid = quote['bid']
        
        # 4. Calculate Indicators
        cost_pct = 0.01
        if exchange == "RH" and ask > 0:
            cost_pct = (ask - current_bid) / ask
            if cost_pct < 0.01:
                cost_pct = 0.01
        
        target_profit = max(cost_pct * profit_mult, 0.01)
        target_dip = min((cost_pct * dip_mult) * -1, -0.05)
        
        current_val = qty_avail * current_bid
        
        # Mode Determination
        mode = "WATCH"
        profit_pct = 0.0
        
        if current_val > 1.00:
            mode = "RISK_ON"
            if total_invested <= 0:
                total_invested = current_val
            profit_pct = (current_val - total_invested) / total_invested
        else:
            if last_ref == 0:
                last_ref = current_bid
            profit_pct = (current_bid - last_ref) / last_ref
        
        # 5. UI Output
        status_icon = "🟢" if can_buy else "👀"
        print(f"{status_icon} {symbol:<12} [{exchange}] | {mode:<8} | "
              f"P/L: {profit_pct*100:6.2f}% | Price: ${current_bid:.4f}")
        
        # 6. Update State (consolidated - once per coin)
        updates = {
            "last_seen_price": current_bid,
            "last_profit_pct": profit_pct,
            "current_value_usd": current_val
        }
        if mode == "WATCH" and last_ref == 0:
            updates["last_reference_price"] = current_bid
        
        # 7. EXECUTION
        
        # --- SELL ---
        if mode == "RISK_ON" and profit_pct >= target_profit:
            bug.success(f"🚀 {symbol} HIT TARGET ({profit_pct*100:.2f}%)! Selling...")
            
            res = unified_place_order(symbol, "sell", qty_avail, exchange, 
                                     dry_run=self.config.dry_run)
            
            if res:
                bug.success("✅ Sell Order Placed.")
                updates["total_invested"] = 0.0
                updates["last_reference_price"] = current_bid
        
        # --- BUY ---
        elif can_buy and profit_pct <= target_dip:
            if (time.time() - last_buy_ts) > self.config.cooldown:
                buying_power = get_account_buying_power(exchange)
                
                if buying_power >= self.config.default_buy_usd:
                    bug.warn(f"📉 {symbol} DIP DETECTED ({profit_pct*100:.2f}%)! Buying...")
                    
                    amount_to_send = self.config.default_buy_usd
                    # If RH, convert USD to Qty String
                    if exchange == "RH":
                        amount_to_send = rh_smart_quantity(symbol, 
                                                           self.config.default_buy_usd, 
                                                           ask)
                        if float(amount_to_send) == 0:
                            update_coin_state(symbol, updates)
                            return
                    
                    res = unified_place_order(symbol, "buy", amount_to_send, exchange,
                                            dry_run=self.config.dry_run)
                    
                    if res:
                        bug.success(f"✅ Bought {symbol}!")
                        updates["total_invested"] = total_invested + self.config.default_buy_usd
                        updates["last_buy_time"] = time.time()
                else:
                    bug.error(f"Not enough funds on {exchange} to buy {symbol}")
        
        # Write all updates once
        update_coin_state(symbol, updates)
    
    def run_scan(self) -> None:
        """Execute a single scan of all coins in the portfolio."""
        portfolio = load_portfolio()
        if not portfolio:
            bug.warn("Portfolio empty. Please add coins first.")
            return
        
        print(f"\n--- SCAN: {time.strftime('%H:%M:%S')} ---")
        
        # Fetch holdings once for this scan
        self._holdings_cache = self._fetch_holdings_once()
        
        rh_count = 0
        cb_count = 0
        
        # Process coins (concurrently if max_workers > 0)
        if self.config.max_workers > 0:
            with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
                futures = []
                for symbol, data in portfolio.items():
                    future = executor.submit(self._process_coin_safe, symbol, data)
                    futures.append((future, data))
                
                for future, data in futures:
                    try:
                        future.result()
                        if data.get('exchange') == 'RH':
                            rh_count += 1
                        else:
                            cb_count += 1
                    except Exception as e:
                        bug.error(f"Error in concurrent processing", e)
        else:
            # Sequential processing
            for symbol, data in portfolio.items():
                try:
                    self.process_coin(symbol, data)
                    if data.get('exchange') == 'RH':
                        rh_count += 1
                    else:
                        cb_count += 1
                except Exception as e:
                    bug.error(f"Error processing {symbol}", e)
        
        print(f"--- Checked: {rh_count} RH | {cb_count} CB ---")
    
    def _process_coin_safe(self, symbol: str, data: Dict[str, Any]) -> None:
        """
        Wrapper for process_coin with exception handling.
        
        Args:
            symbol: Coin symbol
            data: Coin state data
        """
        try:
            self.process_coin(symbol, data)
        except Exception as e:
            bug.error(f"Error processing {symbol}", e)
    
    def run_loop(self) -> None:
        """
        Run the main trading loop.
        
        Continuously scans portfolio and processes coins until interrupted.
        """
        self.running = True
        bug.section("Starting Trading Loop")
        
        if self.config.dry_run:
            bug.warn("⚠️  DRY RUN MODE ENABLED - No real orders will be placed")
        
        print(f"{bug.BLUE}Press CTRL+C to stop and return.{bug.ENDC}")
        
        try:
            while self.running:
                self.run_scan()
                print(f"Sleeping for {self.config.scan_interval} seconds...")
                time.sleep(self.config.scan_interval)
        except KeyboardInterrupt:
            bug.log("\nStopping Trader...")
            self.running = False
