import os
import uuid
import datetime
import json
from decimal import Decimal, ROUND_DOWN
from dotenv import load_dotenv
from coinbase.rest import RESTClient
from bugeater import bug

# Load environment variables immediately
load_dotenv(override=True)

class CoinbaseAPI:
    def __init__(self, log_dir="."):
        
        self.log_dir = log_dir
        
        # Load Keys from ENV
        self.api_key = os.environ.get("CB_API_KEY")
        self.private_key = os.environ.get("CB_PRIVATE_KEY")
        
        # Define Log Paths
        self.open_log_file = os.path.join(log_dir, "OPEN.log")
        self.close_log_file = os.path.join(log_dir, "CLOSE.log")
        
        # Initialize Client
        bug.log("Initializing Coinbase Client...", label="CB-API")
        self.client = self._load_client()

    def _load_client(self):
        if not self.api_key or not self.private_key:
            bug.error("Missing CB_API_KEY or CB_PRIVATE_KEY in .env")
            return None
            
        try:
            client = RESTClient(api_key=self.api_key, api_secret=self.private_key)
            bug.success("Coinbase SDK initialized.")
            return client
        except Exception as e:
            bug.error(f"Failed to initialize Coinbase Client: {e}")
            return None

    # === LOGGING UTILITIES ===

    def _timestamp(self):
        return datetime.datetime.utcnow().isoformat()

    # === POSITION TRACKING (FILE BASED) ===

    def log_trade_open(self, trade_id, symbol, qty, price):
        dt = self._timestamp().replace(":", "")
        line = f"OPEN::{trade_id}:{dt}:{symbol}:{qty}:{price}:\n"
        try:
            with open(self.open_log_file, "a") as f: f.write(line)
        except Exception as e:
            bug.error(f"Failed to write OPEN log: {e}")

    def log_trade_close(self, trade_id, symbol, qty, price, pnl):
        dt = self._timestamp()
        line = f"CLOSE::{trade_id}:{dt}:{symbol}:{qty}:{price}:{pnl}\n"
        try:
            with open(self.close_log_file, "a") as f: f.write(line)
        except Exception as e:
            bug.error(f"Failed to write CLOSE log: {e}")

    def find_open_trade(self, symbol):
        if not os.path.exists(self.open_log_file): return None
        with open(self.open_log_file, "r") as f:
            for line in f:
                if f":{symbol}:" in line: return line.strip().rstrip(":")
        return None

    def remove_open_trade(self, symbol):
        if not os.path.exists(self.open_log_file): return
        with open(self.open_log_file, "r") as f: lines = f.readlines()
        with open(self.open_log_file, "w") as f:
            for line in lines:
                if f":{symbol}:" not in line: f.write(line)

    # === MARKET DATA & UTILS ===

    def get_precision(self, symbol):
        if not self.client: return 8
        try:
            product = self.client.get_product(symbol)
            base_increment = getattr(product, "base_increment", None) or product.get("base_increment", "0.00000001")
            return abs(Decimal(str(base_increment)).as_tuple().exponent)
        except Exception as e:
            bug.error(f"Precision fetch failed for {symbol}: {e}")
            return 8

    def get_current_price(self, symbol):
        if not self.client: return None
        try:
            product = self.client.get_product(symbol)
            price = getattr(product, "price", None) or product.get("price")
            bug.log(f"Fetched CB Price for {symbol}: {price}", label="CB-DATA")
            return float(price)
        except Exception as e:
            bug.error(f"Price fetch failed for {symbol}: {e}")
            return None

    def get_usdc_balance(self):
        """Fetches the USDC balance specifically."""
        if not self.client: return 0.0
        try:
            response = self.client.get_accounts()
            accounts = getattr(response, "accounts", []) if hasattr(response, "accounts") else response.get("accounts", [])
            
            for acc in accounts:
                curr = getattr(acc, "currency", None) or (acc.get("currency") if hasattr(acc, "get") else None)
                
                # STRICTLY CHECK FOR USDC
                if curr == "USDC":
                    bal_obj = getattr(acc, "available_balance", None) or (acc.get("available_balance") if hasattr(acc, "get") else {})
                    val = getattr(bal_obj, "value", 0) if hasattr(bal_obj, "value") else bal_obj.get("value", 0)
                    bug.log(f"CB USDC Balance: {val}")
                    return float(val)
            return 0.0
        except Exception as e:
            bug.error(f"Balance fetch failed: {e}")
            return 0.0

    # === TRADING ACTIONS ===

    def buy(self, symbol, usdc_amount):
        """Executes a Market Buy using USDC."""
        if not self.client: return None
        
        # Safety Check: Ensure symbol ends in USDC
        if not symbol.endswith("-USDC"):
            bug.warn(f"Auto-correcting {symbol} to {symbol}-USDC for Coinbase")
            symbol = f"{symbol}-USDC"

        if self.find_open_trade(symbol):
            bug.warn(f"Skipping BUY for {symbol}: Position already open.")
            return None

        price = self.get_current_price(symbol)
        if not price: return None
        
        precision = self.get_precision(symbol)
        raw_qty = Decimal(str(usdc_amount)) / Decimal(str(price))
        qty = raw_qty.quantize(Decimal(10) ** -precision, rounding=ROUND_DOWN)

        bug.log(f"Preparing BUY: {symbol} | ${usdc_amount} / ${price} = {qty}")

        try:
            trade_id = str(uuid.uuid4())
            order = self.client.create_order(
                client_order_id=trade_id,
                product_id=symbol,
                side="BUY",
                order_configuration={"market_market_ioc": {"base_size": str(qty)}}
            )
            short_id = trade_id[:8]
            self.log_trade_open(short_id, symbol, qty, price)
            bug.success(f"BUY EXECUTED: {symbol} | {qty} units @ ${price}")
            return order

        except Exception as e:
            bug.error(f"BUY Order Failed: {e}")
            return None

    def sell(self, symbol):
        if not self.client: return None
        
        if not symbol.endswith("-USDC"):
            symbol = f"{symbol}-USDC"

        open_line = self.find_open_trade(symbol)
        if not open_line:
            bug.warn(f"Skipping SELL for {symbol}: No open position found.")
            return None

        try:
            parts = open_line.split("::")[1].split(":")
            trade_id, _, _, qty_str, entry_price_str = parts[:5]
            qty = float(qty_str)
            entry_price = float(entry_price_str)
        except Exception as e:
            bug.error(f"Corrupt log line for {symbol}: {e}")
            return None

        price = self.get_current_price(symbol)
        if not price: return None

        try:
            bug.log(f"Executing SELL for {symbol}: {qty} units")
            order = self.client.create_order(
                client_order_id=str(uuid.uuid4()),
                product_id=symbol,
                side="SELL",
                order_configuration={"market_market_ioc": {"base_size": str(qty)}}
            )

            pnl = round((price - entry_price) * qty, 2)
            self.remove_open_trade(symbol)
            self.log_trade_close(trade_id, symbol, qty, price, pnl)
            bug.success(f"SELL EXECUTED: {symbol} | P/L: ${pnl}")
            return order

        except Exception as e:
            bug.error(f"SELL Order Failed: {e}")
            return None
