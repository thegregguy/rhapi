"""
Core Trader class with concurrency, proper profit calculation, and dry-run support.
"""
import time
import logging
from decimal import Decimal, ROUND_DOWN
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Optional

from bugeater import bug
from setcoin import load_portfolio, update_coin_state, clear_portfolio_cache
from .config import Config
from .exchanges import (
    get_unified_quote,
    get_unified_holdings,
    unified_place_order,
    get_account_buying_power,
    rh_smart_quantity,
    normalize_symbol
)


class Trader:
    """
    Modular trader with concurrency, configuration, and dry-run support.
    """
    
    def __init__(self, config: Optional[Config] = None):
        """Initialize trader with configuration."""
        self.config = config or Config()
        self.logger = logging.getLogger('trader')
        
        # Log configuration
        self.logger.info(f"Trader initialized with {self.config}")
        
        if self.config.AUTO_DRY_RUN:
            self.logger.warning("DRY-RUN MODE ENABLED - No real orders will be placed")
            bug.warn("DRY-RUN MODE ENABLED - No real orders will be placed")
    
    def calculate_profit_pct(self, symbol: str, state: Dict, current_val: Decimal, 
                            current_bid: Decimal) -> tuple:
        """
        Calculate profit percentage correctly.
        
        Fix for bug: total_invested should not be overwritten with current value.
        
        Returns:
            (profit_pct, mode, total_invested_used)
        """
        total_invested = Decimal(str(state.get("total_invested", 0.0)))
        last_ref = Decimal(str(state.get("last_reference_price", 0.0)))
        
        mode = "WATCH"
        profit_pct = Decimal("0.0")
        total_invested_used = total_invested
        
        # Debug logging
        if self.config.LOG_LEVEL == "DEBUG":
            self.logger.debug(
                f"{symbol}: qty_val={current_val}, total_invested={total_invested}, "
                f"last_ref={last_ref}, current_bid={current_bid}"
            )
        
        if current_val > Decimal("1.00"):
            mode = "RISK_ON"
            
            # FIX: Only use current_val as fallback if total_invested is truly zero
            if total_invested > Decimal("0.0"):
                # We have a recorded investment - use it
                profit_pct = (current_val - total_invested) / total_invested
                total_invested_used = total_invested
            elif last_ref > Decimal("0.0"):
                # Fallback to last_reference_price
                profit_pct = (current_bid - last_ref) / last_ref
                self.logger.warning(
                    f"{symbol}: No total_invested, using last_reference_price={last_ref}"
                )
            else:
                # No data - mark as unknown
                profit_pct = Decimal("0.0")
                total_invested_used = current_val
                self.logger.warning(
                    f"{symbol}: No total_invested or last_reference_price, P/L unknown"
                )
        else:
            # WATCH mode - use reference price
            if last_ref == Decimal("0.0"):
                last_ref = current_bid
            profit_pct = (current_bid - last_ref) / last_ref if last_ref > 0 else Decimal("0.0")
        
        return float(profit_pct), mode, float(total_invested_used)
    
    def process_coin(self, symbol: str, state: Dict, holdings_map: Dict) -> Optional[str]:
        """
        Process a single coin. Returns status message or None.
        
        Args:
            symbol: Trading symbol
            state: Coin state from portfolio
            holdings_map: Map of symbol -> holding info from get_unified_holdings()
        """
        try:
            exchange = state.get("exchange", "RH")
            
            # Load settings
            total_invested = Decimal(str(state.get("total_invested", 0.0)))
            last_ref = Decimal(str(state.get("last_reference_price", 0.0)))
            last_buy_ts = state.get("last_buy_time", 0)
            can_buy = state.get("can_buy", False)
            profit_mult = Decimal(str(state.get("profit_mult", 2.0)))
            dip_mult = Decimal(str(state.get("dip_mult", 3.0)))
            
            # Get quantity from pre-fetched holdings
            qty_avail = Decimal("0.0")
            if symbol in holdings_map and holdings_map[symbol]['exchange'] == exchange:
                qty_avail = Decimal(str(holdings_map[symbol]['qty']))
            
            # Get price quote
            quote = get_unified_quote(symbol, exchange)
            if not quote:
                return f"⚠️  {symbol}: No quote available"
            
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
            
            # Calculate profit using fixed logic
            profit_pct, mode, total_invested_used = self.calculate_profit_pct(
                symbol, state, current_val, current_bid
            )
            profit_pct_decimal = Decimal(str(profit_pct))
            
            # UI Output
            status_icon = "🟢" if can_buy else "👀"
            status_msg = (
                f"{status_icon} {symbol:<12} [{exchange}] | {mode:<8} | "
                f"P/L: {profit_pct*100:6.2f}% | Price: ${float(current_bid):.4f}"
            )
            
            # Update state (consolidated - single write per coin per scan)
            updates = {
                "last_seen_price": float(current_bid),
                "last_profit_pct": profit_pct,
                "current_value_usd": float(current_val)
            }
            
            if mode == "WATCH" and last_ref == 0:
                updates["last_reference_price"] = float(current_bid)
            
            # EXECUTION LOGIC
            
            # --- SELL ---
            if mode == "RISK_ON" and profit_pct_decimal >= target_profit:
                self.logger.info(
                    f"{symbol} HIT TARGET ({profit_pct*100:.2f}%)! "
                    f"{'[DRY-RUN] Would sell' if self.config.AUTO_DRY_RUN else 'Selling'}..."
                )
                
                if self.config.AUTO_DRY_RUN:
                    # Dry-run mode - don't actually place order
                    status_msg += f" | [DRY-RUN] Would SELL {float(qty_avail):.6f}"
                else:
                    # Real mode - place order
                    res = unified_place_order(symbol, "sell", float(qty_avail), exchange)
                    
                    if res:
                        bug.success(f"✅ Sell Order Placed for {symbol}")
                        updates.update({
                            "total_invested": 0.0,
                            "last_reference_price": float(current_bid)
                        })
                        status_msg += " | SOLD ✅"
                        time.sleep(2)
                    else:
                        status_msg += " | SELL FAILED ❌"
            
            # --- BUY ---
            elif can_buy and profit_pct_decimal <= target_dip:
                if (time.time() - last_buy_ts) > self.config.AUTO_COOLDOWN:
                    buying_power = get_account_buying_power(exchange)
                    
                    if buying_power >= self.config.AUTO_BUY_USD:
                        self.logger.info(
                            f"{symbol} DIP DETECTED ({profit_pct*100:.2f}%)! "
                            f"{'[DRY-RUN] Would buy' if self.config.AUTO_DRY_RUN else 'Buying'}..."
                        )
                        
                        if self.config.AUTO_DRY_RUN:
                            # Dry-run mode - don't actually place order
                            status_msg += f" | [DRY-RUN] Would BUY ${self.config.AUTO_BUY_USD:.2f}"
                        else:
                            # Real mode - place order
                            amount_to_send = self.config.AUTO_BUY_USD
                            
                            # If RH, convert USD to Qty String
                            if exchange == "RH":
                                amount_to_send = rh_smart_quantity(
                                    symbol, self.config.AUTO_BUY_USD, float(ask)
                                )
                                if float(amount_to_send) == 0:
                                    status_msg += " | BUY QTY TOO SMALL"
                                    update_coin_state(symbol, updates)
                                    return status_msg
                            
                            res = unified_place_order(symbol, "buy", amount_to_send, exchange)
                            
                            if res:
                                bug.success(f"✅ Bought {symbol}!")
                                updates.update({
                                    "total_invested": float(total_invested + Decimal(str(self.config.AUTO_BUY_USD))),
                                    "last_buy_time": time.time()
                                })
                                status_msg += " | BOUGHT ✅"
                                time.sleep(2)
                            else:
                                status_msg += " | BUY FAILED ❌"
                    else:
                        status_msg += f" | INSUFFICIENT FUNDS (${buying_power:.2f})"
                else:
                    status_msg += " | COOLDOWN"
            
            # Write consolidated updates
            update_coin_state(symbol, updates)
            
            return status_msg
            
        except Exception as e:
            self.logger.error(f"Error processing {symbol}", exc_info=True)
            return f"❌ {symbol}: {str(e)}"
    
    def run_scan(self):
        """
        Run a single scan of all coins in portfolio.
        Fetches holdings once and processes coins concurrently.
        """
        # Clear cache at start of scan
        clear_portfolio_cache()
        
        portfolio = load_portfolio(use_cache=True)
        if not portfolio:
            self.logger.warning("Portfolio is empty")
            return
        
        # Fetch holdings once per scan
        self.logger.info("Fetching holdings...")
        holdings_list = get_unified_holdings()
        holdings_map = {h['symbol']: h for h in holdings_list}
        
        self.logger.info(f"Processing {len(portfolio)} coins with {self.config.MAX_WORKERS} workers")
        
        # Process coins concurrently
        if self.config.MAX_WORKERS > 1:
            with ThreadPoolExecutor(max_workers=self.config.MAX_WORKERS) as executor:
                futures = {
                    executor.submit(self.process_coin, symbol, state, holdings_map): symbol
                    for symbol, state in portfolio.items()
                }
                
                for future in as_completed(futures):
                    symbol = futures[future]
                    try:
                        result = future.result()
                        if result:
                            print(result)
                    except Exception as e:
                        self.logger.error(f"Failed to process {symbol}", exc_info=True)
        else:
            # Sequential processing
            for symbol, state in portfolio.items():
                result = self.process_coin(symbol, state, holdings_map)
                if result:
                    print(result)
        
        # Clear cache after scan
        clear_portfolio_cache()
    
    def run_loop(self):
        """
        Run the trading loop continuously.
        """
        self.logger.info("Starting trading loop")
        bug.section("Starting Auto Trader")
        
        if self.config.AUTO_DRY_RUN:
            print(f"{bug.WARNING}🔸 DRY-RUN MODE - No real orders will be placed 🔸{bug.ENDC}")
        
        try:
            while True:
                print(f"\n--- SCAN: {time.strftime('%H:%M:%S')} ---")
                
                self.run_scan()
                
                print(f"--- Sleeping for {self.config.SCAN_INTERVAL}s ---")
                time.sleep(self.config.SCAN_INTERVAL)
                
        except KeyboardInterrupt:
            self.logger.info("Trading loop stopped by user")
            bug.log("\nStopping Trader...")
