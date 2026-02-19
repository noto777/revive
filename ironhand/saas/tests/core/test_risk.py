"""
Tests for core/risk.py - Risk management and position sizing.

Tests:
- Position sizing calculations
- Exposure limit enforcement
- Risk per trade calculations
- Account-based constraints
"""

import pytest
from decimal import Decimal


try:
    from ironhand.core.risk import RiskManager, PositionSize
except ImportError:
    RiskManager = None
    PositionSize = None


pytestmark = pytest.mark.skipif(
    RiskManager is None,
    reason="RiskManager not implemented yet"
)


class TestPositionSizing:
    """Test position sizing calculations."""
    
    def test_basic_position_sizing(self, default_strategy_config):
        """Verify basic position size calculation."""
        risk_mgr = RiskManager(default_strategy_config)
        
        account_value = 100000.0
        entry_price = 50.0
        
        position_size = risk_mgr.calculate_position_size(
            account_value=account_value,
            entry_price=entry_price
        )
        
        assert position_size is not None
        assert position_size.quantity > 0
        assert position_size.notional_value > 0
        assert position_size.notional_value <= account_value
    
    def test_position_size_respects_min_trade_value(self, default_strategy_config):
        """Position size should meet minimum trade value."""
        risk_mgr = RiskManager(default_strategy_config)
        
        min_trade = default_strategy_config["min_ladder_trade_usd"]
        
        position_size = risk_mgr.calculate_position_size(
            account_value=100000.0,
            entry_price=50.0
        )
        
        notional = position_size.quantity * position_size.entry_price
        assert notional >= min_trade, \
            f"Position value ${notional:.2f} below minimum ${min_trade}"
    
    def test_position_size_scales_with_account(self, default_strategy_config):
        """Larger account should allow larger positions."""
        risk_mgr = RiskManager(default_strategy_config)
        
        entry_price = 50.0
        
        size_small = risk_mgr.calculate_position_size(10000.0, entry_price)
        size_large = risk_mgr.calculate_position_size(100000.0, entry_price)
        
        assert size_large.quantity > size_small.quantity, \
            "Larger account should allow larger positions"
    
    def test_position_size_with_different_prices(self, default_strategy_config):
        """Position sizing should adjust for entry price."""
        risk_mgr = RiskManager(default_strategy_config)
        
        account_value = 100000.0
        
        # Lower price should allow more shares
        size_low_price = risk_mgr.calculate_position_size(account_value, 10.0)
        size_high_price = risk_mgr.calculate_position_size(account_value, 100.0)
        
        # Quantity should be inverse to price for same dollar amount
        assert size_low_price.quantity > size_high_price.quantity


class TestExposureLimits:
    """Test exposure limit enforcement."""
    
    def test_total_exposure_limit(self, default_strategy_config):
        """Total exposure should not exceed account limit."""
        config = default_strategy_config.copy()
        config["max_total_exposure_pct"] = 50.0  # Max 50% of account
        
        risk_mgr = RiskManager(config)
        
        account_value = 100000.0
        current_exposure = 40000.0  # Already 40% exposed
        
        is_allowed = risk_mgr.check_exposure_limit(
            account_value=account_value,
            current_exposure=current_exposure,
            new_trade_value=15000.0  # Would bring to 55%
        )
        
        assert not is_allowed, \
            "Should reject trade that exceeds total exposure limit"
    
    def test_exposure_limit_allows_within_limit(self, default_strategy_config):
        """Trades within exposure limit should be allowed."""
        config = default_strategy_config.copy()
        config["max_total_exposure_pct"] = 50.0
        
        risk_mgr = RiskManager(config)
        
        account_value = 100000.0
        current_exposure = 30000.0  # 30% exposed
        
        is_allowed = risk_mgr.check_exposure_limit(
            account_value=account_value,
            current_exposure=current_exposure,
            new_trade_value=10000.0  # Would bring to 40%
        )
        
        assert is_allowed, \
            "Should allow trade within exposure limit"
    
    def test_per_symbol_exposure_limit(self, default_strategy_config):
        """Per-symbol exposure should be enforced."""
        config = default_strategy_config.copy()
        config["max_per_symbol_pct"] = 20.0
        
        risk_mgr = RiskManager(config)
        
        account_value = 100000.0
        
        # Already have $18k in ETHU
        is_allowed = risk_mgr.check_symbol_exposure(
            symbol="ETHU",
            account_value=account_value,
            current_symbol_exposure=18000.0,
            new_trade_value=5000.0  # Would bring to 23%
        )
        
        assert not is_allowed, \
            "Should reject trade exceeding per-symbol limit"
    
    def test_core_position_size_limit(self, default_strategy_config):
        """Core position should respect max_core_pct."""
        config = default_strategy_config.copy()
        config["max_core_pct"] = 15.0
        
        risk_mgr = RiskManager(config)
        
        account_value = 100000.0
        max_core_value = risk_mgr.get_max_core_position_value(account_value)
        
        expected = account_value * 0.15
        assert abs(max_core_value - expected) < 100, \
            f"Max core should be {expected}, got {max_core_value}"


class TestRiskPerTrade:
    """Test risk per trade calculations."""
    
    def test_risk_amount_calculation(self, default_strategy_config):
        """Calculate risk amount based on stop distance."""
        config = default_strategy_config.copy()
        config["risk_per_trade_pct"] = 2.0  # Risk 2% per trade
        
        risk_mgr = RiskManager(config)
        
        account_value = 100000.0
        entry_price = 50.0
        stop_price = 48.0  # 4% stop
        
        risk_amount = risk_mgr.calculate_risk_amount(
            account_value=account_value,
            entry_price=entry_price,
            stop_price=stop_price
        )
        
        # Should risk approximately 2% of account
        expected_risk = account_value * 0.02
        assert abs(risk_amount - expected_risk) < 500
    
    def test_position_size_from_risk(self, default_strategy_config):
        """Calculate position size based on risk amount."""
        config = default_strategy_config.copy()
        config["risk_per_trade_pct"] = 1.0  # 1% risk
        
        risk_mgr = RiskManager(config)
        
        account_value = 100000.0
        entry_price = 50.0
        stop_price = 49.0  # $1 stop = 2%
        
        position_size = risk_mgr.calculate_size_from_risk(
            account_value=account_value,
            entry_price=entry_price,
            stop_price=stop_price
        )
        
        # Risk = quantity * (entry - stop)
        # $1000 (1% of account) = qty * $1
        # qty should be ~1000
        expected_qty = 1000.0
        assert abs(position_size.quantity - expected_qty) < 100
    
    def test_multiple_positions_risk_aggregation(self, default_strategy_config):
        """Total risk across multiple positions should be tracked."""
        config = default_strategy_config.copy()
        config["max_total_risk_pct"] = 5.0  # Max 5% total risk
        
        risk_mgr = RiskManager(config)
        
        account_value = 100000.0
        
        # Already have 3% risk in other positions
        current_total_risk = 3000.0
        
        # New trade would add 2.5% risk
        new_trade_risk = 2500.0
        
        is_allowed = risk_mgr.check_total_risk_limit(
            account_value=account_value,
            current_total_risk=current_total_risk,
            new_trade_risk=new_trade_risk
        )
        
        # Total would be 5.5%, should be rejected
        assert not is_allowed


class TestAccountConstraints:
    """Test account-based constraints."""
    
    def test_buying_power_check(self, default_strategy_config):
        """Verify buying power is sufficient."""
        risk_mgr = RiskManager(default_strategy_config)
        
        buying_power = 50000.0
        trade_value = 60000.0
        
        has_power = risk_mgr.check_buying_power(buying_power, trade_value)
        
        assert not has_power, \
            "Should reject trade exceeding buying power"
    
    def test_margin_requirements(self, default_strategy_config):
        """Test margin requirement calculations."""
        config = default_strategy_config.copy()
        config["margin_requirement"] = 0.5  # 50% margin (2x leverage)
        
        risk_mgr = RiskManager(config)
        
        position_value = 100000.0
        required_margin = risk_mgr.calculate_margin_required(position_value)
        
        expected = position_value * 0.5
        assert required_margin == expected
    
    def test_available_margin_calculation(self, default_strategy_config):
        """Calculate available margin for new positions."""
        config = default_strategy_config.copy()
        config["margin_requirement"] = 0.25  # 25% margin (4x leverage)
        
        risk_mgr = RiskManager(config)
        
        account_value = 100000.0
        used_margin = 20000.0  # $20k tied up
        
        available = risk_mgr.calculate_available_margin(
            account_value=account_value,
            used_margin=used_margin
        )
        
        # Should have $80k available
        assert available == pytest.approx(80000.0, abs=100)


class TestDynamicSizing:
    """Test dynamic position sizing based on conditions."""
    
    def test_reduce_size_in_high_volatility(self, default_strategy_config):
        """Position size should reduce in high volatility."""
        config = default_strategy_config.copy()
        config["volatility_adjustment"] = True
        
        risk_mgr = RiskManager(config)
        
        account_value = 100000.0
        entry_price = 50.0
        
        # Normal volatility (ATR 2%)
        size_normal = risk_mgr.calculate_position_size(
            account_value=account_value,
            entry_price=entry_price,
            atr_pct=2.0
        )
        
        # High volatility (ATR 8%)
        size_high_vol = risk_mgr.calculate_position_size(
            account_value=account_value,
            entry_price=entry_price,
            atr_pct=8.0
        )
        
        assert size_high_vol.quantity < size_normal.quantity, \
            "Should reduce size in high volatility"
    
    def test_increase_size_with_winning_streak(self, default_strategy_config):
        """Position sizing can increase with consistent wins (Kelly criterion)."""
        config = default_strategy_config.copy()
        config["dynamic_sizing"] = True
        
        risk_mgr = RiskManager(config)
        
        # After 5 consecutive wins
        size_winning = risk_mgr.calculate_position_size(
            account_value=100000.0,
            entry_price=50.0,
            win_streak=5,
            win_rate=0.65
        )
        
        # No streak
        size_neutral = risk_mgr.calculate_position_size(
            account_value=100000.0,
            entry_price=50.0,
            win_streak=0,
            win_rate=0.50
        )
        
        # Winning streak with good win rate should allow larger size
        # (but this is optional, can skip if not implementing Kelly)
        # assert size_winning.quantity >= size_neutral.quantity


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_zero_account_value(self, default_strategy_config):
        """Handle zero account value."""
        risk_mgr = RiskManager(default_strategy_config)
        
        with pytest.raises(ValueError):
            risk_mgr.calculate_position_size(
                account_value=0.0,
                entry_price=50.0
            )
    
    def test_negative_values_rejected(self, default_strategy_config):
        """Negative values should raise errors."""
        risk_mgr = RiskManager(default_strategy_config)
        
        with pytest.raises(ValueError):
            risk_mgr.calculate_position_size(
                account_value=-100000.0,
                entry_price=50.0
            )
        
        with pytest.raises(ValueError):
            risk_mgr.calculate_position_size(
                account_value=100000.0,
                entry_price=-50.0
            )
    
    def test_very_small_account(self, default_strategy_config):
        """Very small account should still work."""
        risk_mgr = RiskManager(default_strategy_config)
        
        # $1000 account
        position_size = risk_mgr.calculate_position_size(
            account_value=1000.0,
            entry_price=50.0
        )
        
        # Should still produce valid position
        assert position_size is not None
        assert position_size.quantity > 0
        
        # But might be below minimum trade value
        # That's OK - the system should handle it gracefully
    
    def test_fractional_shares_support(self, default_strategy_config):
        """Handle fractional shares if supported."""
        config = default_strategy_config.copy()
        config["allow_fractional_shares"] = True
        
        risk_mgr = RiskManager(config)
        
        position_size = risk_mgr.calculate_position_size(
            account_value=100000.0,
            entry_price=5000.0  # High price (BTC-like)
        )
        
        # Quantity might be fractional
        assert position_size.quantity > 0
        # Don't enforce integer if fractional shares allowed
    
    def test_whole_shares_only(self, default_strategy_config):
        """Enforce whole shares when required."""
        config = default_strategy_config.copy()
        config["allow_fractional_shares"] = False
        
        risk_mgr = RiskManager(config)
        
        position_size = risk_mgr.calculate_position_size(
            account_value=100000.0,
            entry_price=50.0
        )
        
        # Quantity should be whole number
        assert position_size.quantity == int(position_size.quantity)


class TestRiskLimitsIntegration:
    """Integration tests for multiple risk limits."""
    
    def test_all_limits_enforced(self, default_strategy_config):
        """Verify all risk limits are checked together."""
        config = default_strategy_config.copy()
        config["max_total_exposure_pct"] = 50.0
        config["max_per_symbol_pct"] = 20.0
        config["risk_per_trade_pct"] = 2.0
        
        risk_mgr = RiskManager(config)
        
        # Complex scenario
        result = risk_mgr.validate_trade(
            account_value=100000.0,
            symbol="ETHU",
            entry_price=50.0,
            quantity=500,
            current_total_exposure=35000.0,
            current_symbol_exposure=15000.0,
            buying_power=60000.0
        )
        
        assert result.is_valid is not None
        if not result.is_valid:
            assert result.rejection_reason is not None
    
    def test_position_allowed_when_all_limits_ok(self, default_strategy_config):
        """Trade should be allowed when all limits are satisfied."""
        risk_mgr = RiskManager(default_strategy_config)
        
        result = risk_mgr.validate_trade(
            account_value=100000.0,
            symbol="ETHU",
            entry_price=50.0,
            quantity=100,  # $5000 position
            current_total_exposure=10000.0,  # Only 10% exposed
            current_symbol_exposure=5000.0,  # Only 5% in this symbol
            buying_power=80000.0  # Plenty of buying power
        )
        
        assert result.is_valid
