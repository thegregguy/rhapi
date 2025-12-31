import base64
import datetime
import json
import os
from typing import Any, Dict, Optional
import requests
from nacl.signing import SigningKey
from dotenv import load_dotenv
from bugeater import bug 

load_dotenv(override=True)

API_KEY = os.environ.get("API_KEY")
BASE64_PRIVATE_KEY = os.environ.get("BASE64_PRIVATE_KEY")

class CryptoAPITrading:
    def __init__(self):
        if not API_KEY or not BASE64_PRIVATE_KEY:
            bug.error("API_KEY or BASE64_PRIVATE_KEY missing in .env")
            return
        
        self.api_key = API_KEY
        bug.log(f"RH API Initialized with Key: {self.api_key[:10]}...")

        try:
            private_key_seed = base64.b64decode(BASE64_PRIVATE_KEY)
            self.private_key = SigningKey(private_key_seed)
        except Exception as e:
            bug.error("Failed to decode private key", e)
            
        self.base_url = "https://trading.robinhood.com"

    @staticmethod
    def _get_current_timestamp() -> int:
        return int(datetime.datetime.now(tz=datetime.timezone.utc).timestamp())

    @staticmethod
    def get_query_params(key: str, *args: Optional[str]) -> str:
        if not args: return ""
        params = [f"{key}={arg}" for arg in args]
        return "?" + "&".join(params)

    def make_api_request(self, method: str, path: str, body: str = "") -> Any:
        timestamp = self._get_current_timestamp()
        headers = self.get_authorization_header(method, path, body, timestamp)
        url = self.base_url + path

        bug.log(f"Request: {method} {path}", label="RH-API")
        
        try:
            if method == "GET":
                response = requests.get(url, headers=headers, timeout=10)
            elif method == "POST":
                json_body = json.loads(body) if body else {}
                bug.inspect(json_body, label="POST Payload")
                response = requests.post(url, headers=headers, json=json_body, timeout=10)
            
            if response.status_code != 200:
                bug.warn(f"API {response.status_code}: {response.text}")
                return None
            
            data = response.json()
            # Only inspect if it's not a massive list (heuristic)
            if "results" not in data or len(data.get("results", [])) < 5:
                bug.inspect(data, label="API Response")
            else:
                bug.log(f"Response received: {len(data.get('results', []))} items.")
                
            return data
        except Exception as e:
            bug.error(f"Request failed: {url}", e)
            return None

    def get_authorization_header(self, method: str, path: str, body: str, timestamp: int) -> Dict[str, str]:
        message_to_sign = f"{self.api_key}{timestamp}{path}{method}{body}"
        signed = self.private_key.sign(message_to_sign.encode("utf-8"))
        return {
            "x-api-key": self.api_key,
            "x-signature": base64.b64encode(signed.signature).decode("utf-8"),
            "x-timestamp": str(timestamp),
        }

    def get_account(self) -> Any:
        return self.make_api_request("GET", "/api/v1/crypto/trading/accounts/")

    def get_trading_pairs(self, *symbols: Optional[str]) -> Any:
        query = self.get_query_params("symbol", *symbols)
        return self.make_api_request("GET", f"/api/v1/crypto/trading/trading_pairs/{query}")

    def get_holdings(self, *asset_codes: Optional[str]) -> Any:
        query = self.get_query_params("asset_code", *asset_codes)
        return self.make_api_request("GET", f"/api/v1/crypto/trading/holdings/{query}")

    def get_best_bid_ask(self, *symbols: Optional[str]) -> Any:
        query = self.get_query_params("symbol", *symbols)
        return self.make_api_request("GET", f"/api/v1/crypto/marketdata/best_bid_ask/{query}")

    def get_orders(self) -> Any:
        return self.make_api_request("GET", "/api/v1/crypto/trading/orders/")

    def place_order(self, client_order_id: str, side: str, order_type: str, symbol: str, order_config: Dict[str, str]) -> Any:
        body = {
            "client_order_id": client_order_id,
            "side": side,
            "type": order_type,
            "symbol": symbol,
            f"{order_type}_order_config": order_config,
        }
        return self.make_api_request("POST", "/api/v1/crypto/trading/orders/", json.dumps(body))

if __name__ == "__main__":
    bug.section("RHAPI.py Debug Mode")
    client = CryptoAPITrading()
    bug.log("Testing Account Connection...")
    acct = client.get_account()
    if acct:
        bug.success("Connection Successful.")
    else:
        bug.error("Connection Failed.")
    
    bug.log("Testing Quote (BTC-USD)...")
    quote = client.get_best_bid_ask("BTC-USD")
