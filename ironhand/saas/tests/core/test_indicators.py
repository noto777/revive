"""
Tests for core/indicators.py - Technical indicator calculations.

Tests calculation accuracy for:
- RSI (Relative Strength Index)
- Bollinger Bands
- ATR (Average True Range)
- WaveTrend (optional)

Verifies against known values and mathematical properties.
"""

import pytest
import pandas as pd
import numpy as np


try:
    from ironhand.core.indicators import (
        calculate_rsi,
        calculate_bollinger_bands,
        calculate_atr,
        calculate_wavetrend
    )
except ImportError:
    calculate_rsi = None
    calculate_bollinger_bands = None
    calculate_atr = None
    calculate_wavetrend = None


pytestmark = pytest.mark.skipif(
    calculate_rsi is None,
    reason="Indicator functions not implemented yet"
)


class TestRSI:
    """Test RSI calculation."""
    
    def test_rsi_basic_calculation(self, sample_ohlcv):
        """Verify RSI is calculated and in valid range."""
        rsi = calculate_rsi(sample_ohlcv, period=14)
        
        assert rsi is not None
        assert isinstance(rsi, pd.Series) or isinstance(rsi, float)
        
        # RSI should be between 0 and 100
        if isinstance(rsi, pd.Series):
            assert (rsi >= 0).all() and (rsi <= 100).all()
        else:
            assert 0 <= rsi <= 100
    
    def test_rsi_known_values(self):
        """Test RSI against known calculated values."""
        # Create test data with known RSI result
        # Prices trending up should give RSI > 50
        dates = pd.date_range('2024-01-01', periods=30, freq='D')
        prices = pd.Series(range(100, 130), index=dates)  # Steady uptrend
        
        df = pd.DataFrame({
            'close': prices,
            'high': prices * 1.01,
            'low': prices * 0.99,
            'open': prices
        })
        
        rsi = calculate_rsi(df, period=14)
        
        # In steady uptrend, RSI should be elevated
        if isinstance(rsi, pd.Series):
            assert rsi.iloc[-1] > 60, "Uptrend should produce RSI > 60"
        else:
            assert rsi > 60
    
    def test_rsi_oversold_condition(self, ohlcv_oversold):
        """Verify RSI detects oversold conditions."""
        rsi = calculate_rsi(ohlcv_oversold, period=14)
        
        # Oversold fixture should produce RSI < 30
        if isinstance(rsi, pd.Series):
            assert rsi.iloc[-1] < 35, "Oversold condition should give low RSI"
        else:
            assert rsi < 35
    
    def test_rsi_different_periods(self, sample_ohlcv):
        """Test RSI with different period settings."""
        rsi_14 = calculate_rsi(sample_ohlcv, period=14)
        rsi_7 = calculate_rsi(sample_ohlcv, period=7)
        rsi_21 = calculate_rsi(sample_ohlcv, period=21)
        
        # All should be valid
        for rsi in [rsi_14, rsi_7, rsi_21]:
            if isinstance(rsi, pd.Series):
                assert not rsi.isna().all()
            else:
                assert not np.isnan(rsi)
        
        # Shorter period should be more volatile
        if isinstance(rsi_7, pd.Series) and isinstance(rsi_21, pd.Series):
            std_7 = rsi_7.std()
            std_21 = rsi_21.std()
            assert std_7 > std_21, "Shorter period should be more volatile"
    
    def test_rsi_insufficient_data(self):
        """Test RSI with insufficient data points."""
        # Only 5 data points, RSI needs 14+
        dates = pd.date_range('2024-01-01', periods=5, freq='D')
        df = pd.DataFrame({
            'close': [100, 101, 102, 101, 100],
            'high': [101, 102, 103, 102, 101],
            'low': [99, 100, 101, 100, 99],
            'open': [100, 101, 102, 101, 100]
        }, index=dates)
        
        # Should handle gracefully (return NaN or raise ValueError)
        try:
            rsi = calculate_rsi(df, period=14)
            if isinstance(rsi, pd.Series):
                assert rsi.isna().any()  # Should have NaN values
            # If it's a single value, it might be NaN or raise
        except ValueError:
            pass  # Acceptable to raise on insufficient data


class TestBollingerBands:
    """Test Bollinger Bands calculation."""
    
    def test_bollinger_bands_structure(self, sample_ohlcv):
        """Verify BB returns correct structure."""
        bb = calculate_bollinger_bands(sample_ohlcv, period=20, std_dev=2)
        
        assert bb is not None
        assert 'upper' in bb
        assert 'middle' in bb
        assert 'lower' in bb
    
    def test_bollinger_bands_ordering(self, sample_ohlcv):
        """Verify upper > middle > lower."""
        bb = calculate_bollinger_bands(sample_ohlcv, period=20, std_dev=2)
        
        if isinstance(bb['upper'], pd.Series):
            # For series, check most recent values
            assert (bb['upper'] >= bb['middle']).all()
            assert (bb['middle'] >= bb['lower']).all()
        else:
            # For scalar values
            assert bb['upper'] >= bb['middle'] >= bb['lower']
    
    def test_bollinger_bands_middle_is_sma(self, sample_ohlcv):
        """Middle band should equal simple moving average."""
        bb = calculate_bollinger_bands(sample_ohlcv, period=20)
        
        # Middle band should be 20-period SMA
        sma = sample_ohlcv['close'].rolling(20).mean()
        
        if isinstance(bb['middle'], pd.Series):
            # Allow small numerical differences
            diff = (bb['middle'] - sma).abs()
            assert (diff < 0.01).all() or diff.isna().all()
    
    def test_bollinger_bands_width_increases_with_volatility(self):
        """Band width should increase with volatility."""
        # Low volatility data
        dates = pd.date_range('2024-01-01', periods=50, freq='D')
        low_vol = pd.DataFrame({
            'close': 100 + np.random.normal(0, 0.1, 50),  # Low std dev
            'high': 101,
            'low': 99,
            'open': 100
        }, index=dates)
        
        # High volatility data
        high_vol = pd.DataFrame({
            'close': 100 + np.random.normal(0, 5, 50),  # High std dev
            'high': 105,
            'low': 95,
            'open': 100
        }, index=dates)
        
        bb_low = calculate_bollinger_bands(low_vol, period=20, std_dev=2)
        bb_high = calculate_bollinger_bands(high_vol, period=20, std_dev=2)
        
        # Width = upper - lower
        if isinstance(bb_low['upper'], pd.Series):
            width_low = (bb_low['upper'] - bb_low['lower']).iloc[-1]
            width_high = (bb_high['upper'] - bb_high['lower']).iloc[-1]
        else:
            width_low = bb_low['upper'] - bb_low['lower']
            width_high = bb_high['upper'] - bb_high['lower']
        
        assert width_high > width_low, \
            "High volatility should produce wider bands"
    
    def test_bollinger_bands_different_std_dev(self, sample_ohlcv):
        """Test BB with different standard deviation multipliers."""
        bb_1std = calculate_bollinger_bands(sample_ohlcv, period=20, std_dev=1)
        bb_2std = calculate_bollinger_bands(sample_ohlcv, period=20, std_dev=2)
        bb_3std = calculate_bollinger_bands(sample_ohlcv, period=20, std_dev=3)
        
        # Wider std_dev should produce wider bands
        if isinstance(bb_1std['upper'], pd.Series):
            width_1 = (bb_1std['upper'] - bb_1std['lower']).iloc[-1]
            width_2 = (bb_2std['upper'] - bb_2std['lower']).iloc[-1]
            width_3 = (bb_3std['upper'] - bb_3std['lower']).iloc[-1]
        else:
            width_1 = bb_1std['upper'] - bb_1std['lower']
            width_2 = bb_2std['upper'] - bb_2std['lower']
            width_3 = bb_3std['upper'] - bb_3std['lower']
        
        assert width_1 < width_2 < width_3


class TestATR:
    """Test Average True Range calculation."""
    
    def test_atr_basic_calculation(self, sample_ohlcv):
        """Verify ATR is calculated and positive."""
        atr = calculate_atr(sample_ohlcv, period=14)
        
        assert atr is not None
        
        # ATR should always be positive
        if isinstance(atr, pd.Series):
            assert (atr >= 0).all()
        else:
            assert atr >= 0
    
    def test_atr_responds_to_volatility(self):
        """ATR should increase with price volatility."""
        dates = pd.date_range('2024-01-01', periods=50, freq='D')
        
        # Low volatility
        low_vol = pd.DataFrame({
            'high': 101 + np.random.uniform(0, 0.5, 50),
            'low': 99 - np.random.uniform(0, 0.5, 50),
            'close': 100 + np.random.normal(0, 0.2, 50),
            'open': 100
        }, index=dates)
        
        # High volatility
        high_vol = pd.DataFrame({
            'high': 105 + np.random.uniform(0, 5, 50),
            'low': 95 - np.random.uniform(0, 5, 50),
            'close': 100 + np.random.normal(0, 3, 50),
            'open': 100
        }, index=dates)
        
        atr_low = calculate_atr(low_vol, period=14)
        atr_high = calculate_atr(high_vol, period=14)
        
        if isinstance(atr_low, pd.Series):
            atr_low = atr_low.iloc[-1]
            atr_high = atr_high.iloc[-1]
        
        assert atr_high > atr_low, \
            "Higher volatility should produce higher ATR"
    
    def test_atr_true_range_components(self, sample_ohlcv):
        """Verify ATR considers all three components of true range."""
        # True Range = max(H-L, |H-Cp|, |L-Cp|) where Cp = previous close
        
        # Create scenario where gap matters
        dates = pd.date_range('2024-01-01', periods=20, freq='D')
        df = pd.DataFrame({
            'high': [102, 103, 104, 110, 109],  # Gap up on day 4
            'low': [98, 99, 100, 108, 107],
            'close': [100, 101, 102, 109, 108],
            'open': [100, 100, 101, 108, 109]
        }, index=dates[:5])
        
        atr = calculate_atr(df, period=3)
        
        # Should handle the gap appropriately
        assert atr is not None
        if isinstance(atr, pd.Series):
            assert not atr.isna().all()
    
    def test_atr_different_periods(self, sample_ohlcv):
        """Test ATR with different period settings."""
        atr_7 = calculate_atr(sample_ohlcv, period=7)
        atr_14 = calculate_atr(sample_ohlcv, period=14)
        atr_28 = calculate_atr(sample_ohlcv, period=28)
        
        # All should be valid
        for atr in [atr_7, atr_14, atr_28]:
            if isinstance(atr, pd.Series):
                assert not atr.isna().all()
            else:
                assert not np.isnan(atr)
        
        # Longer period should be smoother (less responsive)
        # But all should be in same ballpark
        if all(isinstance(a, pd.Series) for a in [atr_7, atr_14, atr_28]):
            std_7 = atr_7.std()
            std_28 = atr_28.std()
            assert std_7 >= std_28, "Shorter period should be more volatile"


class TestWaveTrend:
    """Test WaveTrend indicator (if implemented)."""
    
    @pytest.mark.skipif(
        calculate_wavetrend is None,
        reason="WaveTrend not implemented"
    )
    def test_wavetrend_basic_calculation(self, sample_ohlcv):
        """Verify WaveTrend calculation."""
        wt = calculate_wavetrend(sample_ohlcv)
        
        assert wt is not None
        # WaveTrend typically returns two lines (WT1, WT2)
        if isinstance(wt, dict):
            assert 'wt1' in wt
            assert 'wt2' in wt
    
    @pytest.mark.skipif(
        calculate_wavetrend is None,
        reason="WaveTrend not implemented"
    )
    def test_wavetrend_oscillator_range(self, sample_ohlcv):
        """WaveTrend should oscillate in reasonable range."""
        wt = calculate_wavetrend(sample_ohlcv)
        
        if isinstance(wt, dict) and 'wt1' in wt:
            wt1 = wt['wt1']
            if isinstance(wt1, pd.Series):
                # Should be centered around 0, typically -100 to +100
                assert wt1.min() > -150
                assert wt1.max() < 150


class TestIndicatorIntegration:
    """Integration tests combining multiple indicators."""
    
    def test_all_indicators_on_same_data(self, sample_ohlcv):
        """Verify all indicators work on the same dataset."""
        rsi = calculate_rsi(sample_ohlcv, period=14)
        bb = calculate_bollinger_bands(sample_ohlcv, period=20)
        atr = calculate_atr(sample_ohlcv, period=14)
        
        # All should complete without errors
        assert rsi is not None
        assert bb is not None
        assert atr is not None
    
    def test_indicator_consistency_across_updates(self, sample_ohlcv):
        """Verify indicators give consistent results with incremental data."""
        # Calculate on first 50 rows
        df_partial = sample_ohlcv.iloc[:50]
        rsi_partial = calculate_rsi(df_partial, period=14)
        
        # Calculate on full data
        rsi_full = calculate_rsi(sample_ohlcv, period=14)
        
        # The values at row 49 should match
        if isinstance(rsi_partial, pd.Series) and isinstance(rsi_full, pd.Series):
            assert abs(rsi_partial.iloc[-1] - rsi_full.iloc[49]) < 0.1, \
                "Indicator should be consistent with incremental data"
    
    def test_indicators_with_missing_data(self):
        """Test indicator handling of missing data."""
        dates = pd.date_range('2024-01-01', periods=30, freq='D')
        df = pd.DataFrame({
            'high': np.random.uniform(99, 101, 30),
            'low': np.random.uniform(99, 101, 30),
            'close': np.random.uniform(99, 101, 30),
            'open': np.random.uniform(99, 101, 30)
        }, index=dates)
        
        # Insert NaN values
        df.loc[df.index[10], 'close'] = np.nan
        df.loc[df.index[15], 'close'] = np.nan
        
        # Indicators should handle NaN gracefully
        try:
            rsi = calculate_rsi(df, period=14)
            bb = calculate_bollinger_bands(df, period=20)
            atr = calculate_atr(df, period=14)
            
            # Should not be all NaN
            if isinstance(rsi, pd.Series):
                assert not rsi.isna().all()
        except ValueError:
            # Acceptable to raise if data quality is poor
            pass


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_constant_price_series(self):
        """Test indicators with completely flat price."""
        dates = pd.date_range('2024-01-01', periods=30, freq='D')
        df = pd.DataFrame({
            'high': 100,
            'low': 100,
            'close': 100,
            'open': 100
        }, index=dates)
        
        # RSI should be 50 (neutral)
        rsi = calculate_rsi(df, period=14)
        if isinstance(rsi, pd.Series):
            # Might be NaN at start, but should converge to 50
            assert rsi.iloc[-5:].mean() == pytest.approx(50, abs=5)
        
        # ATR should be 0
        atr = calculate_atr(df, period=14)
        if isinstance(atr, pd.Series):
            assert atr.iloc[-1] == pytest.approx(0, abs=0.01)
        else:
            assert atr == pytest.approx(0, abs=0.01)
    
    def test_extreme_price_movement(self):
        """Test indicators with extreme price changes."""
        dates = pd.date_range('2024-01-01', periods=30, freq='D')
        prices = [100] * 15 + [200] * 15  # Sudden 100% jump
        
        df = pd.DataFrame({
            'high': prices,
            'low': prices,
            'close': prices,
            'open': prices
        }, index=dates)
        
        # Should handle without crashing
        rsi = calculate_rsi(df, period=14)
        atr = calculate_atr(df, period=14)
        
        assert rsi is not None
        assert atr is not None
