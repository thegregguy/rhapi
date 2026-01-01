"""
Core trading logic module.

Contains the main Trader class that orchestrates trading operations.
"""

import time
from typing import Dict, Any, Optional, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from bugeater import bug
from setcoin import load_portfolio, update_coin_state
from .config import Config
from .exchanges import ExchangeAdapter


class Trader:
    """
    Main trading class that orchestrates buy/sell decisions.
    
    Features:
    - Fetches holdings once per scan (cached)
    - Optional concurrency for processing multiple coins
    - DRY_RUN mode support
    - No per-coin sleep delays
    """
    
    def __init__(self, config: Config, exchange_adapter: ExchangeAdapter):
        """
        Initialize the Trader.
        
        Args:
            config: Configuration object
            exchange_adapter: Exchange adapter instance
        """
        self.config = config
        self.exchange = exchange_adapter
        self.scan_count = 0
    
    def process_coin(self, symbol: str, state: Dict[str, Any], holdings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process a single coin for trading decisions.
        
        Args:
            symbol: Trading symbol (e.g., BTC-USD)
            state: Portfolio state for this coin
            holdings: Pre-fetched holdings list
            
        Returns:
            Dict with processing results and statistics
        """
        exchange = state.get("exchange", "RH")
        
        # 1. Load Settings
        total_invested = state.get("total_invested", 0.0)
        last_ref = state.get("last_reference_price", 0.0)
        last_buy_ts = state.get("last_buy_time", 0)
        can_buy = state.get("can_buy", False)
        profit_mult = state.get("profit_mult", 2.0)
        dip_mult = state.get("dip_mult", 3.0)
        
        # 2. Get Live Holdings from pre-fetched data
        qty_avail = 0.0
        for h in holdings:
            # STRICT MATCHING (symbol includes suffix now)
            if h['symbol'] == symbol and h['exchange'] == exchange:
                qty_avail = h['qty']
                break
        
        # 3. Get Price
        quote = self.exchange.get_unified_quote(symbol, exchange)
        if not quote:
            bug.warn(f"No quote for {symbol}")
            return {"status": "no_quote", "symbol": symbol}
        
        ask = quote['ask']
        current_bid = quote['bid']
        
        # 4. Calculate Indicators
        # Simple Logic: If no spread info (CB), assume 1% cost basis
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
        print(f"{status_icon} {symbol:<12} [{exchange}] | {mode:<8} | P/L: {profit_pct*100:6.2f}% | Price: ${current_bid:.4f}")
        
        # 6. Update State
        updates = {
            "last_seen_price": current_bid,
            "last_profit_pct": profit_pct,
            "current_value_usd": current_val
        }
        if mode == "WATCH" and last_ref == 0:
            updates["last_reference_price"] = current_bid
        update_coin_state(symbol, updates)
        
        # 7. EXECUTION
        action_taken = None
        
        # --- SELL ---
        if mode == "RISK_ON" and profit_pct >= target_profit:
            bug.success(f"🚀 {symbol} HIT TARGET ({profit_pct*100:.2f}%)! Selling...")
            
            res = self.exchange.unified_place_order(symbol, "sell", qty_avail, exchange)
            
            if res:
                if self.config.DRY_RUN:
                    bug.success("✅ [DRY_RUN] Sell Order Would Be Placed.")
                else:
                    bug.success("✅ Sell Order Placed.")
                update_coin_state(symbol, {"total_invested": 0.0, "last_reference_price": current_bid})
                action_taken = "sell"
        
        # --- BUY ---
        elif can_buy and profit_pct <= target_dip:
            if (time.time() - last_buy_ts) > self.config.COOLDOWN:
                buying_power = self.exchange.get_account_buying_power(exchange)
                
                if buying_power >= self.config.DEFAULT_BUY_USD:
                    bug.warn(f"📉 {symbol} DIP DETECTED ({profit_pct*100:.2f}%)! Buying...")
                    
                    amount_to_send = self.config.DEFAULT_BUY_USD
                    # If RH, convert USD to Qty String
                    if exchange == "RH":
                        amount_to_send = self.exchange.rh_smart_quantity(symbol, self.config.DEFAULT_BUY_USD, ask)
                        if float(amount_to_send) == 0:
                            return {"status": "insufficient_quantity", "symbol": symbol}
                    
                    res = self.exchange.unified_place_order(symbol, "buy", amount_to_send, exchange)
                    
                    if res:
                        if self.config.DRY_RUN:
                            bug.success(f"✅ [DRY_RUN] Would Buy {symbol}!")
                        else:
                            bug.success(f"✅ Bought {symbol}!")
                        update_coin_state(symbol, {
                            "total_invested": total_invested + self.config.DEFAULT_BUY_USD,
                            "last_buy_time": time.time(),
                        })
                        action_taken = "buy"
                else:
                    bug.error(f"Not enough funds on {exchange} to buy {symbol}")
        
        return {
            "status": "processed",
            "symbol": symbol,
            "exchange": exchange,
            "mode": mode,
            "profit_pct": profit_pct,
            "action": action_taken
        }
    
    def process_coin_wrapper(self, symbol: str, state: Dict[str, Any], holdings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Wrapper for process_coin that handles exceptions.
        
        Args:
            symbol: Trading symbol
            state: Portfolio state
            holdings: Pre-fetched holdings
            
        Returns:
            Processing result dict
        """
        try:
            return self.process_coin(symbol, state, holdings)
        except Exception as e:
            bug.error(f"Error processing {symbol}", e)
            return {"status": "error", "symbol": symbol, "error": str(e)}
    
    def run_single_scan(self) -> Dict[str, Any]:
        """
        Run a single trading scan over all portfolio coins.
        
        Returns:
            Dict with scan statistics
        """
        self.scan_count += 1
        portfolio = load_portfolio()
        
        if not portfolio:
            bug.warn("Portfolio empty. Please add coins first.")
            return {"status": "empty_portfolio"}
        
        # Fetch holdings ONCE for this scan
        self.exchange.invalidate_holdings_cache()
        holdings = self.exchange.get_unified_holdings(use_cache=False)
        
        print(f"\n--- SCAN #{self.scan_count}: {time.strftime('%H:%M:%S')} ---")
        
        rh_count = 0
        cb_count = 0
        results = []
        
        if self.config.USE_CONCURRENCY and len(portfolio) > 1:
            # Concurrent processing
            with ThreadPoolExecutor(max_workers=self.config.MAX_WORKERS) as executor:
                futures = {}
                for symbol, data in portfolio.items():
                    future = executor.submit(self.process_coin_wrapper, symbol, data, holdings)
                    futures[future] = symbol
                
                for future in as_completed(futures):
                    result = future.result()
                    results.append(result)
                    if result.get('exchange') == 'RH':
                        rh_count += 1
                    else:
                        cb_count += 1
        else:
            # Sequential processing
            for symbol, data in portfolio.items():
                result = self.process_coin_wrapper(symbol, data, holdings)
                results.append(result)
                if data.get('exchange') == 'RH':
                    rh_count += 1
                else:
                    cb_count += 1
        
        print(f"--- Checked: {rh_count} RH | {cb_count} CB ---")
        
        return {
            "status": "completed",
            "scan_count": self.scan_count,
            "rh_count": rh_count,
            "cb_count": cb_count,
            "results": results
        }
    
    def run_trading_loop(self) -> None:
        """
        Run the trading loop continuously until interrupted.
        
        Scans at SCAN_INTERVAL and handles KeyboardInterrupt gracefully.
        """
        bug.section("Starting Dual-Exchange Auto Trader")
        if self.config.DRY_RUN:
            print(f"{bug.WARNING}⚠️  DRY_RUN MODE: No real orders will be placed{bug.ENDC}")
        print(f"{bug.BLUE}Press CTRL+C to stop and return to menu.{bug.ENDC}")
        
        try:
            while True:
                self.run_single_scan()
                print(f"Sleeping for {self.config.SCAN_INTERVAL}s...")
                time.sleep(self.config.SCAN_INTERVAL)
        except KeyboardInterrupt:
            bug.log("\nStopping Trader... Returning to Menu.")
            time.sleep(1)
