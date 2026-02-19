import yfinance as yf
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cipher_b
import pandas as pd

# Fetch QQQ Daily for 2020
df = yf.download("QQQ", start="2020-01-01", end="2020-12-31", interval="1d", progress=False)
if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
df.columns = df.columns.str.lower()

# Generate Signals
sig = cipher_b.generate_signals(df)

# Check specifically around March 2020 and Nov 2020
print("\n--- Signal Check: QQQ Daily (March 2020) ---")
target_days_mar = sig.loc['2020-03-01':'2020-03-31']
print(target_days_mar[['close', 'wt1', 'wt2', 'green_dot', 'red_dot']])

print("\n--- Signal Check: QQQ Daily (Nov 2020) ---")
target_days_nov = sig.loc['2020-11-01':'2020-11-30']
print(target_days_nov[['close', 'wt1', 'wt2', 'green_dot', 'red_dot']])
