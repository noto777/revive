import logging
import requests
import json
import os

logger = logging.getLogger(__name__)

class AlpacaClient:
    def __init__(self, user_id=None, api_key=None, secret_key=None, base_url=None):
        """
        Multi-tenant AlpacaClient.
        - user_id: loads creds from user_{id}_alpaca_cred.json
        - api_key/secret_key/base_url: direct creds (backward compatible)
        """
        if user_id:
            self.user_id = user_id
            self.api_key, self.secret_key, self.base_url = self._load_credentials()
        elif api_key and secret_key:
            self.user_id = None
            self.api_key = api_key
            self.secret_key = secret_key
            self.base_url = base_url or "https://paper-api.alpaca.markets"
        else:
            raise ValueError("Provide either user_id or api_key+secret_key")
        
        self.headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key,
            "Content-Type": "application/json"
        }

    def _load_credentials(self):
        credentials_file = f"user_{self.user_id}_alpaca_cred.json"
        credentials_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), credentials_file)
        if not os.path.exists(credentials_path):
            credentials_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'alpaca_cred.json')
        try:
            with open(credentials_path, 'r') as f:
                credentials = json.load(f)
                return credentials['key_id'], credentials['secret_key'], credentials['endpoint']
        except Exception as e:
            logger.error(f"Credential Load Error: {e}")
            raise Exception(f"Failed to load Alpaca credentials for user {self.user_id}")

    def get_real_time_price(self, symbol):
        url = f"https://data.alpaca.markets/v2/stocks/{symbol}/snapshot?feed=iex"
        try:
            r = requests.get(url, headers=self.headers)
            if r.status_code == 200:
                data = r.json()
                if 'latestTrade' in data and data['latestTrade']['p']:
                    return float(data['latestTrade']['p'])
                if 'latestQuote' in data and data['latestQuote']['ap']:
                    return float(data['latestQuote']['ap'])
        except Exception as e:
            logger.error(f"Price Fetch Error: {e}")
        return None

    def get_historical_bars(self, symbol, timeframe="1Day", limit=100):
        url = f"https://data.alpaca.markets/v2/stocks/{symbol}/bars"
        params = {"timeframe": timeframe, "limit": limit, "feed": "iex"}
        try:
            r = requests.get(url, headers=self.headers, params=params)
            if r.status_code == 200:
                data = r.json()
                if 'bars' in data and data['bars']:
                    return data['bars']
        except Exception as e:
            logger.error(f"History Fetch Error: {e}")
        return []

    def get_open_orders(self, symbol=None, side=None):
        url = f"{self.base_url}/v2/orders?status=open"
        if symbol: url += f"&symbols={symbol}"
        r = requests.get(url, headers=self.headers)
        if r.status_code == 200:
            orders = r.json()
            if side:
                orders = [o for o in orders if o['side'] == side]
            return orders
        return []

    def cancel_order(self, order_id):
        url = f"{self.base_url}/v2/orders/{order_id}"
        requests.delete(url, headers=self.headers)

    def cancel_all_orders(self):
        url = f"{self.base_url}/v2/orders"
        requests.delete(url, headers=self.headers)

    def get_account_summary(self):
        url = f"{self.base_url}/v2/account"
        r = requests.get(url, headers=self.headers)
        if r.status_code == 200:
            return r.json()
        return None

    def get_position(self, symbol):
        url = f"{self.base_url}/v2/positions/{symbol}"
        try:
            r = requests.get(url, headers=self.headers)
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 404:
                return None
        except: pass
        return None

    def get_account(self):
        return self.get_account_summary()

    def place_order(self, symbol, qty, side, type="market", limit_price=None, stop_price=None, trail_percent=None, time_in_force="day"):
        url = f"{self.base_url}/v2/orders"
        if limit_price: limit_price = round(float(limit_price), 2)
        if stop_price: stop_price = round(float(stop_price), 2)
        payload = {
            "symbol": symbol, "qty": str(qty), "side": side, "type": type,
            "limit_price": str(limit_price) if limit_price else None,
            "stop_price": str(stop_price) if stop_price else None,
            "trail_percent": str(trail_percent) if trail_percent else None,
            "time_in_force": time_in_force, "extended_hours": True
        }
        payload = {k: v for k, v in payload.items() if v is not None}
        r = requests.post(url, headers=self.headers, json=payload)
        if r.status_code == 200:
            return r.json()['id']
        else:
            logger.error(f"Order Error: {r.text}")
            return None
