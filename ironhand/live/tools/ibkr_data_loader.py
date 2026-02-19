import pandas as pd
from ib_insync import *
import datetime
import time
import os

# CONFIG
HOST = '127.0.0.1'
PORT = 7497 # 7496 for TWS, 4002 for Gateway
CLIENT_ID = 99
# Updated List (No VNQ)
SYMBOLS = ['QQQ', 'SMH', 'XLK', 'IGV', 'IBIT', 'GLD', 'XLE', 'XBI', 'TQQQ', 'SOXL', 'BITX', 'SLV']
EXCHANGE = 'SMART'
CURRENCY = 'USD'
START_DATE = datetime.datetime(2021, 2, 1)
END_DATE = datetime.datetime(2026, 2, 17)
OUTPUT_DIR = 'ibkr_data'

def fetch_data():
    ib = IB()
    try:
        print(f"Connecting to IBKR ({HOST}:{PORT})...")
        ib.connect(HOST, PORT, clientId=CLIENT_ID)
    except Exception as e:
        print(f"Connection failed: {e}")
        print("Make sure TWS/Gateway is running and API connections are enabled.")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for symbol in SYMBOLS:
        print(f"\n--- Processing {symbol} ---")
        contract = Stock(symbol, EXCHANGE, CURRENCY)
        
        try:
            ib.qualifyContracts(contract)
        except Exception as e:
            print(f"Failed to qualify {symbol}: {e}")
            continue

        all_bars = []
        current_end = END_DATE
        
        while current_end > START_DATE:
            print(f"Fetching chunk ending {current_end}...")
            
            bars = ib.reqHistoricalData(
                contract,
                endDateTime=current_end,
                durationStr='1 W',
                barSizeSetting='1 min',
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1
            )
            
            if not bars:
                print("No bars found/Remaining.")
                break
                
            df = util.df(bars)
            if df is not None and not df.empty:
                all_bars.append(df)
                min_date = df['date'].min()
                print(f"  Got {len(df)} bars. Earliest: {min_date}")
                
                if isinstance(min_date, pd.Timestamp):
                    current_end = min_date.to_pydatetime()
                else:
                    current_end = min_date
            else:
                print("Empty dataframe.")
                current_end -= datetime.timedelta(weeks=1)

            time.sleep(2) # Respect pacing

        if all_bars:
            full_df = pd.concat(all_bars)
            full_df = full_df.sort_values('date').drop_duplicates(subset=['date'])
            filename = f"{OUTPUT_DIR}/{symbol}_1min.csv"
            full_df.to_csv(filename, index=False)
            print(f"Saved {len(full_df)} bars to {filename}")
        else:
            print(f"No data collected for {symbol}.")

    ib.disconnect()

if __name__ == "__main__":
    fetch_data()
