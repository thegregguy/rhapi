"""
Core trader implementation.

The Trader class encapsulates the main trading loop logic with:
- Single holdings fetch per scan
- Optional concurrency for processing multiple coins
- Dry-run support
- Decimal-based calculations with float conversion for APIs
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from typing import Dict, Any, Optional, List
from bugeater import bug

from trader.config import Config
from trader.exchanges import (
    get_unified_quote,
    get_unified_holdings,
    unified_place_order,
    get_account_buying_power,
    rh_smart_quantity,
)
from setcoin import load_portfolio, update_coin_state


class Trader:
    """
    Main trader class implementing the automated trading strategy.
    
    The trader:
    - Fetches portfolio holdings once per scan
    - Processes each coin according to its state
    - Executes buy/sell orders based on strategy
    - Supports dry-run mode for testing
    - Optionally uses concurrency for faster scanning
    """
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize the trader.
        
        Args:
            config: Configuration object (creates default if None)
        """
        self.config = config or Config()
        self.holdings_cache: List[Dict[str, Any]] = []
        self.last_holdings_fetch: float = 0
        
        bug.log(f"Trader initialized: {self.config}", label="TRADER")
    
    def _fetch_holdings_for_scan(self) -> None:
        """Fetch and cache holdings for the current scan."""
        bug.log("Fetching unified holdings...", label="TRADER")
        self.holdings_cache = get_unified_holdings()
        self.last_holdings_fetch = time.time()
        bug.log(f"Cached {len(self.holdings_cache)} holdings", label="TRADER")
    
    def _get_coin_quantity(self, symbol: str, exchange: str) -> float:
        """
        Get quantity available for a coin from cached holdings.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange name
        
        Returns:
            Available quantity (0 if not found)
        """
        for h in self.holdings_cache:
            if h['symbol'] == symbol and h['exchange'] == exchange:
                return h['qty']
        return 0.0
    
    def process_coin(self, symbol: str, state: Dict[str, Any]) -> None:
        """
        Process a single coin according to trading strategy.
        
        Args:
            symbol: Trading symbol
            state: Coin state from portfolio
        """
        exchange = state.get("exchange", "RH")
        
        # Load state
        total_invested = Decimal(str(state.get("total_invested", 0.0)))
        last_ref = Decimal(str(state.get("last_reference_price", 0.0)))
        last_buy_ts = state.get("last_buy_time", 0)
        can_buy = state.get("can_buy", False)
        profit_mult = Decimal(str(state.get("profit_mult", 2.0)))
        dip_mult = Decimal(str(state.get("dip_mult", 3.0)))
        
        # Get quantity from cached holdings
        qty_avail = self._get_coin_quantity(symbol, exchange)
        
        # Get current price
        quote = get_unified_quote(symbol, exchange)
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
        
        current_val = Decimal(str(qty_avail)) * current_bid
        
        # Determine mode
        mode = "WATCH"
        profit_pct = Decimal("0")
        needs_ref_update = False
        
        if current_val > Decimal("1.00"):
            mode = "RISK_ON"
            if total_invested <= 0:
                total_invested = current_val
            profit_pct = (current_val - total_invested) / total_invested
        else:
            if last_ref == 0:
                last_ref = current_bid
                needs_ref_update = True  # Flag to update in portfolio
            profit_pct = (current_bid - last_ref) / last_ref
        
        # UI output
        status_icon = "🟢" if can_buy else "👀"
        print(
            f"{status_icon} {symbol:<12} [{exchange}] | {mode:<8} | "
            f"P/L: {float(profit_pct)*100:6.2f}% | Price: ${float(current_bid):.4f}"
        )
        
        # Update state (accumulate changes, write once at end)
        updates = {
            "last_seen_price": float(current_bid),
            "last_profit_pct": float(profit_pct),
            "current_value_usd": float(current_val)
        }
        
        if needs_ref_update:
            updates["last_reference_price"] = float(current_bid)
        
        # Execute trading logic
        executed_trade = False
        
        # SELL logic
        if mode == "RISK_ON" and profit_pct >= target_profit:
            bug.success(
                f"🚀 {symbol} HIT TARGET ({float(profit_pct)*100:.2f}%)! Selling..."
            )
            
            res = unified_place_order(
                symbol, "sell", float(qty_avail), exchange, 
                dry_run=self.config.auto_dry_run
            )
            
            if res or self.config.auto_dry_run:
                bug.success("✅ Sell Order Placed (or dry-run).")
                updates["total_invested"] = 0.0
                updates["last_reference_price"] = float(current_bid)
                executed_trade = True
        
        # BUY logic
        elif can_buy and profit_pct <= target_dip:
            if (time.time() - last_buy_ts) > self.config.cooldown:
                buying_power = get_account_buying_power(exchange)
                
                if buying_power >= float(self.config.default_buy_usd):
                    bug.warn(
                        f"📉 {symbol} DIP DETECTED ({float(profit_pct)*100:.2f}%)! "
                        f"Buying..."
                    )
                    
                    amount_to_send = float(self.config.default_buy_usd)
                    
                    # For RH, convert USD to quantity string
                    if exchange == "RH":
                        amount_to_send = rh_smart_quantity(
                            symbol, float(self.config.default_buy_usd), float(ask)
                        )
                        if float(amount_to_send) == 0:
                            bug.warn(f"Invalid quantity for {symbol}, skipping")
                            update_coin_state(symbol, updates)
                            return
                    
                    res = unified_place_order(
                        symbol, "buy", amount_to_send, exchange,
                        dry_run=self.config.auto_dry_run
                    )
                    
                    if res or self.config.auto_dry_run:
                        bug.success(f"✅ Bought {symbol} (or dry-run)!")
                        updates["total_invested"] = float(
                            total_invested + self.config.default_buy_usd
                        )
                        updates["last_buy_time"] = time.time()
                        executed_trade = True
                else:
                    bug.error(f"Not enough funds on {exchange} to buy {symbol}")
        
        # Write state updates once
        update_coin_state(symbol, updates)
        
        # Small delay after trades to avoid rate limits
        if executed_trade and not self.config.auto_dry_run:
            time.sleep(2)
    
    def run_single_scan(self) -> None:
        """Execute a single scan of the portfolio."""
        portfolio = load_portfolio()
        
        if not portfolio:
            bug.warn("Portfolio empty. Please add coins first.")
            return
        
        # Fetch holdings once for this scan
        self._fetch_holdings_for_scan()
        
        print(f"\n--- SCAN: {time.strftime('%H:%M:%S')} ---")
        
        rh_count = 0
        cb_count = 0
        
        # Process coins
        if self.config.max_workers > 1:
            # Concurrent processing
            with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
                futures = []
                for symbol, data in portfolio.items():
                    future = executor.submit(self.process_coin, symbol, data)
                    futures.append((future, symbol, data))
                
                for future, symbol, data in futures:
                    try:
                        future.result()
                        if data.get('exchange') == 'RH':
                            rh_count += 1
                        else:
                            cb_count += 1
                    except Exception as e:
                        bug.error(f"Error processing {symbol}", e)
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
    
    def run_loop(self) -> None:
        """
        Run the continuous trading loop.
        
        Scans portfolio at configured intervals until interrupted.
        """
        bug.section("Starting Auto Trader Loop")
        
        if self.config.auto_dry_run:
            bug.warn("⚠️  DRY RUN MODE ACTIVE - No real orders will be placed!")
        
        print(f"{bug.BLUE}Press CTRL+C to stop and return to menu.{bug.ENDC}")
        
        try:
            while True:
                self.run_single_scan()
                print(f"Sleeping for {self.config.scan_interval}s...")
                time.sleep(self.config.scan_interval)
        except KeyboardInterrupt:
            bug.log("\nStopping Trader... Returning to Menu.")
            time.sleep(1)
