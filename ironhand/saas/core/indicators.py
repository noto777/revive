"""
Technical Indicators

Pure functions for RSI, Bollinger Bands, ATR, and WaveTrend calculations.
Ported from live bot's indicator_engine.py.

Uses pandas and numpy for vectorized calculations.
No I/O, no side effects - just math.
"""

from typing import Tuple

import numpy as np
import pandas as pd
from scipy.signal import savgol_filter

from exceptions import InvalidIndicatorData
from logger import get_logger

logger = get_logger()


def calculate_rsi(
    data: pd.DataFrame,
    period: int = 14,
    price_column: str = "close"
) -> pd.Series:
    """
    Calculate Relative Strength Index using EWM (Exponential Weighted Moving Average).
    
    Args:
        data: DataFrame with OHLCV data
        period: RSI period (default 14)
        price_column: Column name for price data
        
    Returns:
        Series with RSI values (0-100)
        
    Raises:
        InvalidIndicatorData: If data is insufficient or invalid
        
    Note:
        This is the single source of truth for RSI.
        Eliminates the dual RSI implementation issue from live bot.
    """
    if len(data) < period + 1:
        raise InvalidIndicatorData(f"Insufficient data for RSI: need {period + 1}, got {len(data)}")
    
    if price_column not in data.columns:
        raise InvalidIndicatorData(f"Column '{price_column}' not found in data")
    
    # Calculate price changes
    delta = data[price_column].diff()
    
    # Separate gains and losses
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    
    # Calculate exponential weighted moving averages
    alpha = 1.0 / period
    avg_gain = gain.ewm(alpha=alpha, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=alpha, min_periods=period, adjust=False).mean()
    
    # Calculate RS and RSI
    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    
    return rsi


def calculate_bollinger_bands(
    data: pd.DataFrame,
    period: int = 20,
    num_std: float = 2.0,
    price_column: str = "close"
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calculate Bollinger Bands (upper, middle, lower).
    
    Args:
        data: DataFrame with OHLCV data
        period: Moving average period (default 20)
        num_std: Number of standard deviations (default 2.0)
        price_column: Column name for price data
        
    Returns:
        Tuple of (upper_band, middle_band, lower_band)
        
    Raises:
        InvalidIndicatorData: If data is insufficient or invalid
    """
    if len(data) < period:
        raise InvalidIndicatorData(f"Insufficient data for BBands: need {period}, got {len(data)}")
    
    if price_column not in data.columns:
        raise InvalidIndicatorData(f"Column '{price_column}' not found in data")
    
    # Middle band is simple moving average
    middle = data[price_column].rolling(window=period).mean()
    
    # Standard deviation
    std = data[price_column].rolling(window=period).std()
    
    # Upper and lower bands
    upper = middle + (std * num_std)
    lower = middle - (std * num_std)
    
    return upper, middle, lower


def calculate_atr(
    data: pd.DataFrame,
    period: int = 14
) -> pd.Series:
    """
    Calculate Average True Range.
    
    Args:
        data: DataFrame with OHLC data (must have 'high', 'low', 'close')
        period: ATR period (default 14)
        
    Returns:
        Series with ATR values
        
    Raises:
        InvalidIndicatorData: If required columns are missing or data insufficient
    """
    required_columns = ['high', 'low', 'close']
    missing = [col for col in required_columns if col not in data.columns]
    if missing:
        raise InvalidIndicatorData(f"Missing required columns for ATR: {missing}")
    
    if len(data) < period + 1:
        raise InvalidIndicatorData(f"Insufficient data for ATR: need {period + 1}, got {len(data)}")
    
    # Calculate True Range components
    high_low = data['high'] - data['low']
    high_close = (data['high'] - data['close'].shift()).abs()
    low_close = (data['low'] - data['close'].shift()).abs()
    
    # True Range is the max of the three
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    
    # ATR is exponential moving average of True Range
    alpha = 1.0 / period
    atr = true_range.ewm(alpha=alpha, min_periods=period, adjust=False).mean()
    
    return atr


def calculate_wavetrend(
    data: pd.DataFrame,
    channel_length: int = 9,
    average_length: int = 12,
    smoothing_length: int = 3,
    price_column: str = "hlc3"
) -> Tuple[pd.Series, pd.Series]:
    """
    Calculate WaveTrend oscillator (WT1, WT2).
    
    WaveTrend is a momentum indicator that uses median price and exponential smoothing.
    
    Args:
        data: DataFrame with OHLC data
        channel_length: EMA period for channel (default 9)
        average_length: EMA period for average (default 12)
        smoothing_length: SMA period for WT2 smoothing (default 3)
        price_column: Price column to use (default hlc3 = (high+low+close)/3)
        
    Returns:
        Tuple of (wt1, wt2) Series
        
    Raises:
        InvalidIndicatorData: If data is insufficient
    """
    # Ensure HLC3 column exists
    if "hlc3" not in data.columns and price_column == "hlc3":
        if not all(col in data.columns for col in ['high', 'low', 'close']):
            raise InvalidIndicatorData("Missing required columns for HLC3 calculation")
        data = data.copy()
        data["hlc3"] = (data["high"] + data["low"] + data["close"]) / 3.0
    
    required_len = max(channel_length, average_length) + smoothing_length
    if len(data) < required_len:
        raise InvalidIndicatorData(f"Insufficient data for WaveTrend: need {required_len}, got {len(data)}")
    
    # Calculate average price
    ap = data[price_column]
    
    # Calculate ESA (Exponential Smoothed Average)
    esa = ap.ewm(span=channel_length, adjust=False).mean()
    
    # Calculate absolute deviation from ESA
    d = (ap - esa).abs()
    d_ema = d.ewm(span=channel_length, adjust=False).mean()
    
    # Calculate CI (Channel Index)
    ci = (ap - esa) / (0.015 * d_ema)
    
    # WT1 is smoothed CI
    wt1 = ci.ewm(span=average_length, adjust=False).mean()
    
    # WT2 is SMA of WT1
    wt2 = wt1.rolling(window=smoothing_length).mean()
    
    return wt1, wt2


def calculate_ema(
    data: pd.Series,
    period: int
) -> pd.Series:
    """
    Calculate Exponential Moving Average.
    
    Args:
        data: Price series
        period: EMA period
        
    Returns:
        EMA series
    """
    return data.ewm(span=period, adjust=False).mean()


def calculate_sma(
    data: pd.Series,
    period: int
) -> pd.Series:
    """
    Calculate Simple Moving Average.
    
    Args:
        data: Price series
        period: SMA period
        
    Returns:
        SMA series
    """
    return data.rolling(window=period).mean()


def smooth_curve(
    data: pd.Series,
    window_length: int = 5,
    polyorder: int = 2
) -> pd.Series:
    """
    Apply Savitzky-Golay smoothing filter.
    
    Args:
        data: Series to smooth
        window_length: Length of filter window (must be odd)
        polyorder: Order of polynomial fit
        
    Returns:
        Smoothed series
    """
    if window_length % 2 == 0:
        window_length += 1  # Must be odd
    
    if len(data) < window_length:
        return data  # Not enough data to smooth
    
    smoothed = savgol_filter(data.values, window_length, polyorder)
    return pd.Series(smoothed, index=data.index)


class IndicatorEngine:
    """
    Wrapper class for indicator functions to match Executor interface.
    """
    
    def calculate_all(self, df: pd.DataFrame, current_price: float) -> dict:
        """
        Calculate all indicators for the latest bar.
        
        Args:
            df: DataFrame with OHLCV data
            current_price: Current market price (unused for calculation, but passed by executor)
            
        Returns:
            Dictionary of latest indicator values
        """
        # Ensure we have enough data
        if len(df) < 50:
            logger.warning("insufficient_data_for_indicators", rows=len(df))
            return {
                'rsi': 0.0,
                'bb_upper': 0.0,
                'bb_middle': 0.0,
                'bb_lower': 0.0,
                'atr': 0.0,
                'wt1': 0.0,
                'wt2': 0.0,
            }
            
        try:
            rsi = calculate_rsi(df)
            upper, middle, lower = calculate_bollinger_bands(df)
            atr = calculate_atr(df)
            wt1, wt2 = calculate_wavetrend(df)
            
            return {
                'rsi': float(rsi.iloc[-1]),
                'bb_upper': float(upper.iloc[-1]),
                'bb_middle': float(middle.iloc[-1]),
                'bb_lower': float(lower.iloc[-1]),
                'atr': float(atr.iloc[-1]),
                'wt1': float(wt1.iloc[-1]),
                'wt2': float(wt2.iloc[-1]),
            }
        except Exception as e:
            logger.error("indicator_calculation_error", error=str(e))
            raise
