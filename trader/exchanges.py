"""
Exchange adapter module.

Provides a unified interface for interacting with multiple exchanges
(Robinhood, Coinbase) with DRY_RUN support.
"""

from typing import Optional, Dict, List, Any
from decimal import Decimal, ROUND_DOWN
import uuid
from bugeater import bug


class ExchangeAdapter:
    """
    Unified exchange adapter that wraps bot.py functions.
    
    Provides caching for holdings and dry-run mode support.
    """
    
    def __init__(self, rh_client, cb_client, config):
        """
        Initialize exchange adapter.
        
        Args:
            rh_client: Robinhood API client
            cb_client: Coinbase API client
            config: Configuration object
        """
        self.rh_client = rh_client
        self.cb_client = cb_client
        self.config = config
        self._holdings_cache: Optional[List[Dict[str, Any]]] = None
    
    def invalidate_holdings_cache(self):
        """Clear the holdings cache to force refresh on next fetch."""
        self._holdings_cache = None
    
    def get_unified_holdings(self, use_cache: bool = True) -> List[Dict[str, Any]]:
        """
        Returns a list of all assets from both exchanges.
        
        Args:
            use_cache: If True and cache exists, return cached holdings
            
        Returns:
            List of dicts with keys: symbol, qty, exchange
        """
        if use_cache and self._holdings_cache is not None:
            bug.log("Using cached holdings", label="EXCHANGE")
            return self._holdings_cache
        
        all_holdings = []
        
        # 1. Robinhood (USD Pairs)
        try:
            res = self.rh_client.get_holdings()
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
            if self.cb_client.client:
                response = self.cb_client.client.get_accounts()
                accts_list = getattr(response, 'accounts', []) if hasattr(response, 'accounts') else response.get('accounts', [])
                
                for acc in accts_list:
                    curr = getattr(acc, 'currency', None) or (acc.get('currency') if hasattr(acc, 'get') else None)
                    
                    # Exclude standard fiat wallets
                    if curr and curr not in ["USD", "USDC"]:
                        bal_obj = getattr(acc, 'available_balance', None) or (acc.get('available_balance') if hasattr(acc, 'get') else {})
                        val = getattr(bal_obj, 'value', 0) if hasattr(bal_obj, 'value') else bal_obj.get('value', 0)
                        
                        bal = float(val)
                        if bal > 0:
                            all_holdings.append({
                                'symbol': f"{curr}-USDC",
                                'qty': bal,
                                'exchange': 'CB'
                            })
        except Exception as e:
            bug.error("Failed to get CB holdings", e)
        
        self._holdings_cache = all_holdings
        return all_holdings
    
    def get_unified_quote(self, symbol: str, exchange: str) -> Optional[Dict[str, float]]:
        """
        Returns a normalized quote dictionary regardless of exchange.
        
        Args:
            symbol: Trading symbol (e.g., BTC-USD, BTC-USDC)
            exchange: Exchange identifier ("RH" or "CB")
            
        Returns:
            Dict with keys: ask, bid, exchange or None if failed
        """
        bug.log(f"Fetching Quote for {symbol} on {exchange}", label="EXCHANGE")
        
        if exchange == "RH":
            # RH always uses -USD
            if "-USDC" in symbol:
                bug.warn(f"Attempted to check {symbol} on RH. Converting to -USD.")
                symbol = symbol.replace("-USDC", "-USD")
            elif "-USD" not in symbol:
                symbol += "-USD"
            
            res = self.rh_client.get_best_bid_ask(symbol)
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
            
            price = self.cb_client.get_current_price(symbol)
            if price:
                return {
                    'ask': price,
                    'bid': price,
                    'exchange': 'CB'
                }
        
        return None
    
    def unified_place_order(self, symbol: str, side: str, quantity_or_dollars: Any, exchange: str) -> Optional[Any]:
        """
        Place an order on the specified exchange.
        
        Respects DRY_RUN mode - if enabled, logs the order but doesn't execute it.
        
        Args:
            symbol: Trading symbol
            side: "buy" or "sell"
            quantity_or_dollars: Amount to trade
            exchange: Exchange identifier ("RH" or "CB")
            
        Returns:
            Order response or None if failed/dry-run
        """
        if self.config.DRY_RUN:
            bug.warn(f"[DRY_RUN] Would place order: {side.upper()} {symbol} ({quantity_or_dollars}) via {exchange}")
            return {"dry_run": True, "message": "Order not placed (DRY_RUN mode)"}
        
        bug.warn(f"ROUTING ORDER: {side.upper()} {symbol} ({quantity_or_dollars}) via {exchange}")
        
        if exchange == "RH":
            # Force USD
            clean_sym = symbol.replace("-USDC", "-USD") if "-USDC" in symbol else symbol
            if "-USD" not in clean_sym:
                clean_sym += "-USD"
            
            return self.rh_client.place_order(
                str(uuid.uuid4()),
                side,
                "market",
                clean_sym,
                {"asset_quantity": str(quantity_or_dollars)}
            )
        
        elif exchange == "CB":
            # Force USDC
            clean_sym = symbol.replace("-USD", "-USDC") if "-USD" in symbol and "-USDC" not in symbol else symbol
            if "-USDC" not in clean_sym:
                clean_sym += "-USDC"
            
            if side == "buy":
                return self.cb_client.buy(clean_sym, float(quantity_or_dollars))
            elif side == "sell":
                return self.cb_client.sell(clean_sym)
        
        return None
    
    def get_account_buying_power(self, exchange: str) -> float:
        """
        Get available buying power for the specified exchange.
        
        Args:
            exchange: Exchange identifier ("RH" or "CB")
            
        Returns:
            Available balance as float
        """
        if exchange == "RH":
            acct = self.rh_client.get_account()
            if acct:
                return float(acct.get('buying_power', 0))
        elif exchange == "CB":
            return self.cb_client.get_usdc_balance()
        return 0.0
    
    def rh_smart_quantity(self, symbol: str, dollars: float, ask_price: float) -> str:
        """
        Calculate valid quantity for Robinhood order based on trading rules.
        
        Args:
            symbol: Trading symbol
            dollars: USD amount to spend
            ask_price: Current ask price
            
        Returns:
            Formatted quantity string
        """
        if "-USD" not in symbol:
            symbol += "-USD"
        if ask_price == 0:
            return "0"
        
        raw_qty = dollars / ask_price
        
        # Import trading rules from bot module
        from bot import TRADING_RULES
        rules = TRADING_RULES.get(symbol)
        if not rules:
            return "{:.6f}".format(raw_qty)
        
        if raw_qty < rules['min_order']:
            return "0"
        
        try:
            inc_str = str(rules['increment'])
            d_qty = Decimal(str(raw_qty))
            d_inc = Decimal(inc_str)
            valid_qty = d_qty.quantize(d_inc, rounding=ROUND_DOWN)
            
            precision = 0
            cleaned = inc_str.rstrip('0')
            if '.' in cleaned:
                precision = len(cleaned.split('.')[1])
            
            # Format with dynamic precision
            format_str = f"{{:.{precision}f}}"
            return format_str.format(valid_qty)
        except:
            return "{:.6f}".format(raw_qty)
