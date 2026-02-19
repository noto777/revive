import pandas as pd
import numpy as np

def calculate_ema(series, span):
    return series.ewm(span=span, adjust=False).mean()

def calculate_sma(series, window):
    return series.rolling(window=window).mean()

def calculate_atr(df, period=14):
    high = df['high']
    low = df['low']
    close = df['close']
    
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # ATR using Wilder's Smoothing (RMA) which is standard in TradingView/Pine
    # Pine's rma(src, len) is equivalent to ema(src, 2*len - 1)
    # But often ATR is just SMA or simple EMA. Standard Pine ATR uses RMA.
    # RMA is EWM with alpha = 1/length
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    return atr

def f_wavetrend(df, chlen=9, avg=12, malen=3):
    """
    Python port of VuManChu Cipher B WaveTrend Oscillator
    """
    # HLC3
    src = (df['high'] + df['low'] + df['close']) / 3.0
    
    # ESA = EMA(src, chlen)
    esa = calculate_ema(src, chlen)
    
    # D = EMA(abs(src - esa), chlen)
    d = calculate_ema(abs(src - esa), chlen)
    
    # CI = (src - esa) / (0.015 * D)
    # Handle division by zero
    ci = (src - esa) / (0.015 * d)
    ci = ci.replace([np.inf, -np.inf], np.nan).fillna(0)
    
    # WT1 = EMA(CI, avg)
    wt1 = calculate_ema(ci, avg)
    
    # WT2 = SMA(WT1, malen)
    wt2 = calculate_sma(wt1, malen)
    
    return wt1, wt2

def calculate_money_flow(df, period=60, multiplier=150, pos_y=2.5):
    """
    RSI+MFI Area calculation
    Pine: sma(((close - open) / (high - low)) * 150, 60) - 2.5
    """
    hl_diff = df['high'] - df['low']
    # Avoid division by zero
    hl_diff = hl_diff.replace(0, np.nan)
    
    raw_mf = ((df['close'] - df['open']) / hl_diff) * multiplier
    raw_mf = raw_mf.fillna(0)
    
    mfi = calculate_sma(raw_mf, period) - pos_y
    return mfi

def generate_signals(df):
    """
    Generates Ladder Bot v3.2 Signals based on Cipher B logic
    """
    # 1. WaveTrend
    wt1, wt2 = f_wavetrend(df)
    
    # 2. Signals
    # Green Dot (Buy): wtCross AND wtCrossUp AND wt2 <= -53
    # Red Dot (Sell): wtCross AND wtCrossDown AND wt2 >= 53
    
    # Crossover logic
    # Cross UP: wt1 crosses ABOVE wt2
    # Current bar: wt1 > wt2, Previous bar: wt1 <= wt2
    wt1_prev = wt1.shift(1)
    wt2_prev = wt2.shift(1)
    
    cross_up = (wt1 > wt2) & (wt1_prev <= wt2_prev)
    cross_down = (wt1 < wt2) & (wt1_prev >= wt2_prev)
    
    # Oversold / Overbought conditions
    os_level = -53
    ob_level = 53
    
    # Note: Pine script 'wt2' in the condition refers to the value at the cross
    green_dot = cross_up & (wt2 <= os_level)
    red_dot = cross_down & (wt2 >= ob_level)
    
    # 3. Money Flow
    money_flow = calculate_money_flow(df)
    
    # 4. MF Velocity (Rate of Change over 3 bars)
    # Using 3 weeks (bars) as specified
    mf_velocity = money_flow.diff(3)
    
    # 5. 200 SMA Filter
    sma200 = calculate_sma(df['close'], 200)
    above_200sma = df['close'] > sma200
    
    # 6. ATR
    atr = calculate_atr(df, 14)
    
    # Combine into result
    result = df.copy()
    result['wt1'] = wt1
    result['wt2'] = wt2
    result['green_dot'] = green_dot
    result['red_dot'] = red_dot
    result['money_flow'] = money_flow
    result['mf_velocity'] = mf_velocity
    result['atr'] = atr
    result['above_200sma'] = above_200sma
    
    return result

if __name__ == "__main__":
    # Simple test if run directly
    print("Cipher B Module Loaded")
