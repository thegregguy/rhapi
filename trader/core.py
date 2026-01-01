"""
Core Trader class with concurrent processing and DRY_RUN support
"""
import time
from decimal import Decimal
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from trader.config import Config
from trader.exchanges import UnifiedExchangeRouter
from setcoin import load_portfolio, update_coin_state
from bugeater import bug


class Trader:
    """Main trader class with concurrent processing support"""
    
    def __init__(self, config: Config = None):
        """Initialize trader with configuration"""
        self.config = config or Config()
        self.router = UnifiedExchangeRouter()
        self.holdings_cache = None
        self.holdings_cache_time = 0
        self.cache_ttl = 30  # Cache TTL in seconds
        
        # Display configuration
        if self.config.AUTO_DRY_RUN:
            bug.warn("🚨 DRY RUN MODE ENABLED - No real orders will be placed!")
    
    def get_holdings(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Get holdings with caching (single fetch per scan)"""
        current_time = time.time()
        
        if force_refresh or not self.holdings_cache or (current_time - self.holdings_cache_time) > self.cache_ttl:
            bug.log("Fetching fresh holdings from exchanges...", label="TRADER")
            self.holdings_cache = self.router.get_all_holdings()
            self.holdings_cache_time = current_time
        
        return self.holdings_cache
    
    def process_coin(self, symbol: str, state: Dict[str, Any]) -> None:
        """Process a single coin (no sleep inside)"""
        exchange = state.get("exchange", "RH")
        
        # Load settings
        total_invested = Decimal(str(state.get("total_invested", 0.0)))
        last_ref = Decimal(str(state.get("last_reference_price", 0.0)))
        last_buy_ts = state.get("last_buy_time", 0)
        can_buy = state.get("can_buy", False)
        profit_mult = Decimal(str(state.get("profit_mult", 2.0)))
        dip_mult = Decimal(str(state.get("dip_mult", 3.0)))
        
        # Get holdings from cache
        holdings = self.get_holdings()
        qty_avail = Decimal("0.0")
        for h in holdings:
            if h['symbol'] == symbol and h['exchange'] == exchange:
                qty_avail = Decimal(str(h['qty']))
                break
        
        # Get price
        quote = self.router.get_quote(symbol, exchange)
        if not quote:
            bug.warn(f"No quote for {symbol}")
            return
        
        ask = Decimal(str(quote['ask']))
        current_bid = Decimal(str(quote['bid']))
        
        # Calculate indicators
        cost_pct = Decimal("0.01")
        if exchange == "RH" and ask > 0:
            cost_pct = (ask - current_bid) / ask
            if cost_pct < Decimal("0.01"):
                cost_pct = Decimal("0.01")
        
        target_profit = max(cost_pct * profit_mult, Decimal("0.01"))
        target_dip = min((cost_pct * dip_mult) * Decimal("-1"), Decimal("-0.05"))
        
        current_val = qty_avail * current_bid
        
        # Mode determination
        mode = "WATCH"
        profit_pct = Decimal("0.0")
        
        if current_val > Decimal("1.00"):
            mode = "RISK_ON"
            if total_invested <= 0:
                total_invested = current_val
            profit_pct = (current_val - total_invested) / total_invested
        else:
            if last_ref == 0:
                last_ref = current_bid
            profit_pct = (current_bid - last_ref) / last_ref
        
        # UI output
        status_icon = "🟢" if can_buy else "👀"
        print(f"{status_icon} {symbol:<12} [{exchange}] | {mode:<8} | P/L: {float(profit_pct)*100:6.2f}% | Price: ${float(current_bid):.4f}")
        
        # Update state
        updates = {
            "last_seen_price": float(current_bid),
            "last_profit_pct": float(profit_pct),
            "current_value_usd": float(current_val)
        }
        if mode == "WATCH" and last_ref == 0:
            updates["last_reference_price"] = float(current_bid)
        update_coin_state(symbol, updates)
        
        # EXECUTION
        
        # --- SELL ---
        if mode == "RISK_ON" and profit_pct >= target_profit:
            bug.success(f"🚀 {symbol} HIT TARGET ({float(profit_pct)*100:.2f}%)! Selling...")
            
            if self.config.AUTO_DRY_RUN:
                bug.warn(f"[DRY RUN] Would sell {float(qty_avail)} {symbol}")
            else:
                res = self.router.place_order(symbol, "sell", float(qty_avail), exchange)
                
                if res:
                    bug.success("✅ Sell Order Placed.")
                    update_coin_state(symbol, {"total_invested": 0.0, "last_reference_price": float(current_bid)})
        
        # --- BUY ---
        elif can_buy and profit_pct <= target_dip:
            if (time.time() - last_buy_ts) > self.config.COOLDOWN:
                buying_power = self.router.get_buying_power(exchange)
                
                if buying_power >= self.config.DEFAULT_BUY_USD:
                    bug.warn(f"📉 {symbol} DIP DETECTED ({float(profit_pct)*100:.2f}%)! Buying...")
                    
                    amount_to_send = self.config.DEFAULT_BUY_USD
                    # If RH, convert USD to Qty String
                    if exchange == "RH":
                        amount_to_send = self.router.smart_quantity(symbol, self.config.DEFAULT_BUY_USD, float(ask), exchange)
                        if float(amount_to_send) == 0:
                            return
                    
                    if self.config.AUTO_DRY_RUN:
                        bug.warn(f"[DRY RUN] Would buy {amount_to_send} {symbol}")
                    else:
                        res = self.router.place_order(symbol, "buy", amount_to_send, exchange)
                        
                        if res:
                            bug.success(f"✅ Bought {symbol}!")
                            update_coin_state(symbol, {
                                "total_invested": float(total_invested) + self.config.DEFAULT_BUY_USD,
                                "last_buy_time": time.time(),
                            })
                else:
                    bug.error(f"Not enough funds on {exchange} to buy {symbol}")
    
    def scan_portfolio(self, portfolio: Dict[str, Any], use_concurrency: bool = True) -> None:
        """Scan all coins in portfolio (optionally with concurrency)"""
        if not portfolio:
            bug.warn("Portfolio is empty")
            return
        
        # Fetch holdings once per scan
        self.get_holdings(force_refresh=True)
        
        if use_concurrency and self.config.MAX_WORKERS > 1:
            # Concurrent processing
            with ThreadPoolExecutor(max_workers=self.config.MAX_WORKERS) as executor:
                futures = {
                    executor.submit(self._safe_process_coin, symbol, data): symbol
                    for symbol, data in portfolio.items()
                }
                
                for future in as_completed(futures):
                    symbol = futures[future]
                    try:
                        future.result()
                    except Exception as e:
                        bug.error(f"Error processing {symbol} in concurrent mode", e)
        else:
            # Sequential processing
            for symbol, data in portfolio.items():
                self._safe_process_coin(symbol, data)
    
    def _safe_process_coin(self, symbol: str, data: Dict[str, Any]) -> None:
        """Safely process a coin with exception handling"""
        try:
            self.process_coin(symbol, data)
        except Exception as e:
            bug.error(f"Error processing {symbol}", e)
    
    def run_loop(self, scan_interval: int = 15):
        """Run continuous trading loop"""
        bug.section("Starting Trader Loop")
        if self.config.AUTO_DRY_RUN:
            bug.warn("🚨 DRY RUN MODE - Monitoring only, no orders will be placed")
        
        try:
            while True:
                portfolio = load_portfolio()
                if not portfolio:
                    bug.warn("Portfolio empty. Please add coins first.")
                    break
                
                print(f"\n--- SCAN: {time.strftime('%H:%M:%S')} ---")
                
                self.scan_portfolio(portfolio)
                
                rh_count = sum(1 for data in portfolio.values() if data.get('exchange') == 'RH')
                cb_count = sum(1 for data in portfolio.values() if data.get('exchange') == 'CB')
                
                print(f"--- Checked: {rh_count} RH | {cb_count} CB ---")
                print(f"Sleeping {scan_interval}s...")
                time.sleep(scan_interval)
                
        except KeyboardInterrupt:
            bug.log("\nStopping Trader...")
