import requests
import json
import pandas as pd
from datetime import datetime

# Load Alpaca Creds
try:
    creds = json.load(open('alpaca_cred.json'))
    API_KEY = creds['key_id']
    SECRET_KEY = creds['secret_key']
    ENDPOINT = "https://data.alpaca.markets/v2" # Data API
except Exception as e:
    print(f"Error loading creds: {e}")
    exit(1)

HEADERS = {
    "APCA-API-KEY-ID": API_KEY,
    "APCA-API-SECRET-KEY": SECRET_KEY
}

def fetch_bars(symbol, start, end):
    url = f"{ENDPOINT}/stocks/{symbol}/bars"
    params = {
        "start": start,
        "end": end,
        "timeframe": "1Min",
        "limit": 10000, # Max limit
        "adjustment": "raw",
        "feed": "iex" # Try Free feed first
    }
    
    print(f"Fetching {symbol} from {start} to {end}...")
    r = requests.get(url, headers=HEADERS, params=params)
    
    if r.status_code == 200:
        data = r.json()
        if "bars" in data and data["bars"]:
            df = pd.DataFrame(data["bars"])
            print(f"Success! Got {len(df)} bars.")
            print(df.head(1))
            print(df.tail(1))
            return True
        else:
            print("Response empty. (Maybe date range too old for IEX feed?)")
            print(data)
            return False
    else:
        print(f"Error {r.status_code}: {r.text}")
        return False

if __name__ == "__main__":
    # Test 1: Recent Data (Should work)
    print("\n--- TEST 1: Recent Data (2024) ---")
    fetch_bars("QQQ", "2024-01-01T09:30:00Z", "2024-01-05T16:00:00Z")
    
    # Test 2: Deep History (2021) - The real test
    print("\n--- TEST 2: Deep History (2021) ---")
    fetch_bars("QQQ", "2021-02-01T09:30:00Z", "2021-02-05T16:00:00Z")
