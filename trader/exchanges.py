"""
Exchange adapters and normalization helpers
Provides unified interface for Robinhood and Coinbase exchanges
"""
import uuid
from decimal import Decimal, ROUND_DOWN
from typing import Dict, List, Optional, Any
from rhapi import CryptoAPITrading
from cbapi import CoinbaseAPI
from bugeater import bug


class ExchangeAdapter:
    """Base class for exchange adapters"""
    
    def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get current quote for symbol"""
        raise NotImplementedError
    
    def get_holdings(self) -> List[Dict[str, Any]]:
        """Get all holdings"""
        raise NotImplementedError
    
    def place_order(self, symbol: str, side: str, quantity_or_dollars: Any) -> Optional[Any]:
        """Place an order"""
        raise NotImplementedError
    
    def get_buying_power(self) -> float:
        """Get available buying power"""
        raise NotImplementedError


class RobinhoodAdapter(ExchangeAdapter):
    """Robinhood exchange adapter"""
    
    def __init__(self):
        self.client = CryptoAPITrading()
        self.trading_rules = {}
        self._load_trading_rules()
    
    def _load_trading_rules(self):
        """Load trading rules from Robinhood"""
        bug.log("Loading Robinhood trading rules...", label="RH-ADAPTER")
        try:
            res = self.client.get_trading_pairs()
            results = res.get('results', []) if isinstance(res, dict) else res
            for item in results:
                sym = item.get('symbol')
                if sym:
                    self.trading_rules[sym] = {
                        "min_order": float(item.get('min_order_size', 0)),
                        "increment": item.get('asset_increment', '0.000001'),
                    }
        except Exception as e:
            bug.error("Failed to load RH trading rules", e)
    
    def normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol for Robinhood (ensure -USD suffix)"""
        if "-USDC" in symbol:
            symbol = symbol.replace("-USDC", "-USD")
        elif "-USD" not in symbol:
            symbol += "-USD"
        return symbol
    
    def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get quote from Robinhood"""
        symbol = self.normalize_symbol(symbol)
        bug.log(f"Fetching quote for {symbol} on RH", label="RH-ADAPTER")
        
        res = self.client.get_best_bid_ask(symbol)
        if res and 'results' in res and len(res['results']) > 0:
            raw = res['results'][0]
            return {
                'ask': float(raw.get('ask_inclusive_of_buy_spread', 0)),
                'bid': float(raw.get('bid_inclusive_of_sell_spread', 0)),
                'exchange': 'RH',
                'symbol': symbol
            }
        return None
    
    def get_holdings(self) -> List[Dict[str, Any]]:
        """Get holdings from Robinhood"""
        holdings = []
        try:
            res = self.client.get_holdings()
            rh_data = res.get('results', []) if res and 'results' in res else []
            for h in rh_data:
                holdings.append({
                    'symbol': h.get('asset_code') + "-USD",
                    'qty': float(h.get('quantity_available_for_trading', 0)),
                    'exchange': 'RH'
                })
        except Exception as e:
            bug.error("Failed to get RH holdings", e)
        return holdings
    
    def place_order(self, symbol: str, side: str, quantity_or_dollars: Any) -> Optional[Any]:
        """Place order on Robinhood"""
        symbol = self.normalize_symbol(symbol)
        bug.warn(f"ROUTING ORDER: {side.upper()} {symbol} ({quantity_or_dollars}) via RH")
        
        return self.client.place_order(
            str(uuid.uuid4()), 
            side, 
            "market", 
            symbol, 
            {"asset_quantity": str(quantity_or_dollars)}
        )
    
    def get_buying_power(self) -> float:
        """Get Robinhood buying power"""
        acct = self.client.get_account()
        if acct:
            return float(acct.get('buying_power', 0))
        return 0.0
    
    def smart_quantity(self, symbol: str, dollars: float, ask_price: float) -> str:
        """Calculate valid quantity for Robinhood based on trading rules"""
        symbol = self.normalize_symbol(symbol)
        
        if ask_price == 0:
            return "0"
        
        raw_qty = dollars / ask_price
        rules = self.trading_rules.get(symbol)
        
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
            
            return f"{{:.{precision}f}}".format(valid_qty)
        except:
            return "{:.6f}".format(raw_qty)


class CoinbaseAdapter(ExchangeAdapter):
    """Coinbase exchange adapter"""
    
    def __init__(self):
        self.client = CoinbaseAPI()
    
    def normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol for Coinbase (ensure -USDC suffix)"""
        if "-USD" in symbol and "-USDC" not in symbol:
            symbol = symbol.replace("-USD", "-USDC")
        elif "-USDC" not in symbol:
            symbol += "-USDC"
        return symbol
    
    def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get quote from Coinbase"""
        symbol = self.normalize_symbol(symbol)
        bug.log(f"Fetching quote for {symbol} on CB", label="CB-ADAPTER")
        
        price = self.client.get_current_price(symbol)
        if price:
            return {
                'ask': price,
                'bid': price,
                'exchange': 'CB',
                'symbol': symbol
            }
        return None
    
    def get_holdings(self) -> List[Dict[str, Any]]:
        """Get holdings from Coinbase"""
        holdings = []
        try:
            if self.client.client:
                response = self.client.client.get_accounts()
                accts_list = getattr(response, 'accounts', []) if hasattr(response, 'accounts') else response.get('accounts', [])
                
                for acc in accts_list:
                    curr = getattr(acc, 'currency', None) or (acc.get('currency') if hasattr(acc, 'get') else None)
                    
                    # Exclude standard fiat wallets
                    if curr and curr not in ["USD", "USDC"]:
                        bal_obj = getattr(acc, 'available_balance', None) or (acc.get('available_balance') if hasattr(acc, 'get') else {})
                        val = getattr(bal_obj, 'value', 0) if hasattr(bal_obj, 'value') else bal_obj.get('value', 0)
                        
                        bal = float(val)
                        if bal > 0:
                            holdings.append({
                                'symbol': f"{curr}-USDC",
                                'qty': bal,
                                'exchange': 'CB'
                            })
        except Exception as e:
            bug.error("Failed to get CB holdings", e)
        return holdings
    
    def place_order(self, symbol: str, side: str, quantity_or_dollars: Any) -> Optional[Any]:
        """Place order on Coinbase"""
        symbol = self.normalize_symbol(symbol)
        bug.warn(f"ROUTING ORDER: {side.upper()} {symbol} ({quantity_or_dollars}) via CB")
        
        if side == "buy":
            return self.client.buy(symbol, float(quantity_or_dollars))
        elif side == "sell":
            return self.client.sell(symbol)
        return None
    
    def get_buying_power(self) -> float:
        """Get Coinbase USDC balance"""
        return self.client.get_usdc_balance()


class UnifiedExchangeRouter:
    """Unified router for both exchanges"""
    
    def __init__(self):
        bug.section("Initializing Unified Exchange Router")
        self.rh = RobinhoodAdapter()
        self.cb = CoinbaseAdapter()
    
    def get_adapter(self, exchange: str) -> ExchangeAdapter:
        """Get the appropriate adapter for the exchange"""
        if exchange == "RH":
            return self.rh
        elif exchange == "CB":
            return self.cb
        else:
            raise ValueError(f"Unknown exchange: {exchange}")
    
    def get_quote(self, symbol: str, exchange: str) -> Optional[Dict[str, Any]]:
        """Get unified quote"""
        adapter = self.get_adapter(exchange)
        return adapter.get_quote(symbol)
    
    def get_all_holdings(self) -> List[Dict[str, Any]]:
        """Get holdings from all exchanges (cached per scan)"""
        all_holdings = []
        all_holdings.extend(self.rh.get_holdings())
        all_holdings.extend(self.cb.get_holdings())
        return all_holdings
    
    def place_order(self, symbol: str, side: str, quantity_or_dollars: Any, exchange: str) -> Optional[Any]:
        """Place unified order"""
        adapter = self.get_adapter(exchange)
        return adapter.place_order(symbol, side, quantity_or_dollars)
    
    def get_buying_power(self, exchange: str) -> float:
        """Get unified buying power"""
        adapter = self.get_adapter(exchange)
        return adapter.get_buying_power()
    
    def smart_quantity(self, symbol: str, dollars: float, ask_price: float, exchange: str) -> str:
        """Calculate smart quantity (Robinhood only)"""
        if exchange == "RH":
            return self.rh.smart_quantity(symbol, dollars, ask_price)
        return str(dollars)  # Coinbase uses dollar amounts directly
