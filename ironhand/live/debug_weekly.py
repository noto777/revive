import yfinance as yf
import pandas as pd
import cipher_b

# Fetch Weekly data for QQQ and IBIT (Bitcoin proxy) for late 2025
tickers = ['QQQ', 'IBIT', 'BTC-USD']
print(f"Checking Weekly Signals for Dec 2025...")

for ticker in tickers:
    print(f"\n--- {ticker} ---")
    df = yf.download(ticker, start="2025-10-01", end="2026-01-01", interval="1wk", progress=False)
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    df.columns = df.columns.str.lower()
    
    # Generate Signals
    sig = cipher_b.generate_signals(df)
    
    # Filter for Dec 2025
    dec_data = sig[sig.index >= '2025-12-01']
    
    for date, row in dec_data.iterrows():
        # Check condition parts
        # wt1 crosses wt2?
        # wt2 <= -53?
        print(f"{date.date()} | WT1: {row['wt1']:.2f} | WT2: {row['wt2']:.2f} | Diff: {row['wt1']-row['wt2']:.2f} | GreenDot: {row['green_dot']}")
        
        if row['green_dot']:
            print("  >>> DETECTED GREEN DOT")
