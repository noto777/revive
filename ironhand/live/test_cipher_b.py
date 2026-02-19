import pytest
import pandas as pd
import yfinance as yf
from cipher_b import generate_signals

SYMBOLS = ['QQQ', 'TQQQ', 'IBIT']

@pytest.fixture(scope="module")
def market_data():
    """
    Fetches 5 years of weekly data for testing
    """
    data = {}
    for sym in SYMBOLS:
        # Download weekly data
        df = yf.download(sym, period="5y", interval="1wk", progress=False)
        
        # Handle yfinance MultiIndex columns (Price, Ticker) -> (Price)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        # Ensure lowercase columns for our module
        df.columns = df.columns.str.lower()
        if 'date' not in df.columns:
            df['date'] = df.index
        data[sym] = df
    return data

def test_signal_generation(market_data):
    for sym, df in market_data.items():
        if df.empty:
            pytest.skip(f"No data for {sym}")
            continue
            
        print(f"Testing {sym} with {len(df)} rows")
        
        results = generate_signals(df)
        
        # 1. Check columns exist
        expected_cols = ['wt1', 'wt2', 'green_dot', 'red_dot', 'money_flow', 'mf_velocity', 'atr', 'above_200sma']
        for col in expected_cols:
            assert col in results.columns, f"Missing {col} in results"
            
        # 2. Check for NaNs in critical columns (after warmup period)
        # WaveTrend needs ~21 bars to stabilize (12 EMA + 9 EMA)
        # 200 SMA needs 200 bars
        
        # Check WaveTrend valid
        valid_wt = results.iloc[25:]
        assert valid_wt['wt1'].notna().all(), "WT1 has NaNs after warmup"
        assert valid_wt['wt2'].notna().all(), "WT2 has NaNs after warmup"
        
        # 3. Check Signal Frequency
        # Signals shouldn't be everywhere, nor zero over 5 years
        green_dots = results['green_dot'].sum()
        red_dots = results['red_dot'].sum()
        
        print(f"{sym} Signals: Green={green_dots}, Red={red_dots}")
        
        assert green_dots > 0, f"No Green Dots found for {sym} in 5 years"
        assert red_dots > 0, f"No Red Dots found for {sym} in 5 years"
        
        # Signals shouldn't be excessively frequent (e.g. > 50% of bars)
        assert green_dots < len(df) * 0.2, "Too many green dots"
        
        # 4. Check Logic Consistency
        # Green Dot = Cross Up AND Oversold
        green_dot_rows = results[results['green_dot']]
        if not green_dot_rows.empty:
            # Check oversold condition (-53)
            # Note: The logic in cipher_b.py uses the CROSS event.
            # Ideally verify that at the signal, wt2 is indeed low.
            assert (green_dot_rows['wt2'] <= -53).all(), "Green dot generated when NOT oversold"

if __name__ == "__main__":
    # Manual run
    data = {}
    for sym in SYMBOLS:
        df = yf.download(sym, period="5y", interval="1wk")
        df.columns = df.columns.str.lower()
        data[sym] = df
        
    test_signal_generation(data)
