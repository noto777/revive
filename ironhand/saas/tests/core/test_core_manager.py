"""
Tests for core/core_manager.py - Exit strategy management.

Tests the CorePositionManager class which handles:
- Rebalancing mode (when core position is too large)
- Standard scale-out mode (progressive profit taking)
- Universal profit lock (trailing stop after threshold)

Focuses on decision logic, not execution.
"""

import pytest
from decimal import Decimal
from typing import List


try:
    from ironhand.core.core_manager import CorePositionManager, SellDecision
except ImportError:
    CorePositionManager = None
    SellDecision = None


pytestmark = pytest.mark.skipif(
    CorePositionManager is None,
    reason="CorePositionManager not implemented yet"
)


class MockPosition:
    """Mock position for testing exit logic."""
    def __init__(self, symbol, quantity, entry_price, current_price):
        self.symbol = symbol
        self.quantity = Decimal(str(quantity))
        self.entry_price = Decimal(str(entry_price))
        self.current_price = Decimal(str(current_price))
        
    @property
    def unrealized_pnl_pct(self) -> float:
        """Calculate unrealized P&L percentage."""
        return float((self.current_price - self.entry_price) / self.entry_price * 100)


class TestRebalancingMode:
    """Test rebalancing mode when core position exceeds limits."""
    
    def test_rebalancing_triggers_above_threshold(self, default_strategy_config):
        """Rebalancing should trigger when position exceeds max + gap."""
        manager = CorePositionManager(default_strategy_config)
        
        account_value = 100000.0
        max_core_pct = default_strategy_config["max_core_pct"]  # 15%
        hysteresis_gap = default_strategy_config["core_hysteresis_gap"]  # 2%
        
        # Position is 18% of account (above 15% + 2% = 17%)
        position_value = account_value * 0.18
        position = MockPosition(
            symbol="ETHU",
            quantity=200,
            entry_price=45.0,
            current_price=50.0  # 11% profit
        )
        
        decision = manager.evaluate_exit_strategy(
            position=position,
            account_value=account_value,
            current_price=50.0
        )
        
        # Should be in rebalancing mode
        assert decision.mode == "rebalancing"
        assert decision.should_sell
    
    def test_rebalancing_scale_out_increments(self, default_strategy_config):
        """Rebalancing should scale out in 5% increments every 2% profit."""
        config = default_strategy_config.copy()
        config["scale_out_pct"] = 5.0  # Explicit for rebalancing
        config["scale_out_step"] = 2.0  # Every 2% profit
        
        manager = CorePositionManager(config)
        
        account_value = 100000.0
        position_value = 18000.0  # 18% of account
        
        # Test at different profit levels
        test_cases = [
            (45.0, 46.0, False),  # 2.2% profit - not yet at first step
            (45.0, 46.8, True),   # 4% profit - should sell
            (45.0, 48.6, True),   # 8% profit - should sell
            (45.0, 50.4, True),   # 12% profit - should sell
        ]
        
        for entry, current, should_sell in test_cases:
            position = MockPosition("ETHU", 200, entry, current)
            decision = manager.evaluate_exit_strategy(
                position, account_value, current
            )
            
            if should_sell:
                assert decision.should_sell, \
                    f"Should sell at {position.unrealized_pnl_pct:.1f}% profit"
            
    def test_rebalancing_exits_when_below_threshold(self, default_strategy_config):
        """Rebalancing should stop when position falls below max_core_pct."""
        manager = CorePositionManager(default_strategy_config)
        
        account_value = 100000.0
        
        # Position is now 14% (below 15% max)
        position_value = 14000.0
        position = MockPosition("ETHU", 200, 45.0, 47.0)  # 4.4% profit
        
        decision = manager.evaluate_exit_strategy(
            position, account_value, 47.0
        )
        
        # Should switch to standard mode or no sell
        assert decision.mode != "rebalancing" or not decision.should_sell


class TestStandardScaleOut:
    """Test standard scale-out mode (progressive profit taking)."""
    
    def test_scale_out_below_first_step(self, default_strategy_config):
        """No sell below first profit step."""
        manager = CorePositionManager(default_strategy_config)
        
        # Position at 6% profit (below 8% first step)
        position = MockPosition("ETHU", 100, 50.0, 53.0)
        
        decision = manager.evaluate_exit_strategy(
            position=position,
            account_value=100000.0,
            current_price=53.0
        )
        
        assert not decision.should_sell, \
            "Should not sell below first profit step"
    
    def test_scale_out_at_first_step(self, default_strategy_config):
        """Should trigger at first profit step (8%)."""
        config = default_strategy_config.copy()
        config["scale_out_pct"] = 15.0
        config["scale_out_step"] = 4.0
        # First step = 2 * step = 8%
        
        manager = CorePositionManager(config)
        
        # Position at 8.5% profit
        position = MockPosition("ETHU", 100, 50.0, 54.25)
        
        decision = manager.evaluate_exit_strategy(
            position, 100000.0, 54.25
        )
        
        assert decision.should_sell
        assert decision.mode == "scale_out"
        # Should sell scale_out_pct (15%)
        expected_qty = position.quantity * Decimal("0.15")
        assert abs(decision.quantity - expected_qty) < Decimal("0.1")
    
    def test_scale_out_progressive_steps(self, default_strategy_config):
        """Verify scale-out at multiple profit levels."""
        config = default_strategy_config.copy()
        config["scale_out_step"] = 4.0
        
        manager = CorePositionManager(config)
        
        test_cases = [
            (50.0, 54.0, True),   # 8% profit - first step
            (50.0, 56.0, True),   # 12% profit - second step
            (50.0, 58.0, True),   # 16% profit - third step
            (50.0, 60.0, True),   # 20% profit - fourth step
        ]
        
        for entry, current, should_sell in test_cases:
            position = MockPosition("ETHU", 100, entry, current)
            decision = manager.evaluate_exit_strategy(
                position, 100000.0, current
            )
            assert decision.should_sell == should_sell
    
    def test_scale_out_quantity_calculation(self, default_strategy_config):
        """Verify correct quantity calculation for scale-out."""
        config = default_strategy_config.copy()
        config["scale_out_pct"] = 20.0  # 20% per step
        
        manager = CorePositionManager(config)
        
        position = MockPosition("ETHU", 100, 50.0, 54.0)  # 8% profit
        
        decision = manager.evaluate_exit_strategy(
            position, 100000.0, 54.0
        )
        
        if decision.should_sell:
            expected = Decimal("20.0")  # 20% of 100
            assert abs(decision.quantity - expected) < Decimal("0.1")


class TestProfitLock:
    """Test universal profit lock (trailing stop)."""
    
    def test_profit_lock_not_armed_below_threshold(self, default_strategy_config):
        """Profit lock should not arm below threshold."""
        config = default_strategy_config.copy()
        config["profit_lock_arm"] = 12.0  # Arms at 12%
        
        manager = CorePositionManager(config)
        
        # Position at 10% profit (below 12%)
        position = MockPosition("ETHU", 100, 50.0, 55.0)
        
        decision = manager.evaluate_exit_strategy(
            position, 100000.0, 55.0
        )
        
        # Profit lock should not be armed
        assert not decision.profit_lock_armed
    
    def test_profit_lock_arms_at_threshold(self, default_strategy_config):
        """Profit lock should arm at threshold."""
        config = default_strategy_config.copy()
        config["profit_lock_arm"] = 12.0
        
        manager = CorePositionManager(config)
        
        # Position at 13% profit (above 12%)
        position = MockPosition("ETHU", 100, 50.0, 56.5)
        
        decision = manager.evaluate_exit_strategy(
            position, 100000.0, 56.5
        )
        
        assert decision.profit_lock_armed
    
    def test_profit_lock_triggers_on_retracement(self, default_strategy_config):
        """Profit lock should trigger when price retraces past trail."""
        config = default_strategy_config.copy()
        config["profit_lock_arm"] = 12.0   # Arms at 12%
        config["profit_lock_trail"] = 4.0  # Trails by 4%
        
        manager = CorePositionManager(config)
        
        # Sequence: position reaches 15%, then retraces to 10%
        # Peak was 15%, trail is 4%, so trigger at 11% (15% - 4%)
        
        # First, establish peak
        position_peak = MockPosition("ETHU", 100, 50.0, 57.5)  # 15%
        decision_peak = manager.evaluate_exit_strategy(
            position_peak, 100000.0, 57.5
        )
        # Manager should track this as peak
        
        # Now retrace to 10%
        position_retrace = MockPosition("ETHU", 100, 50.0, 55.0)  # 10%
        decision_retrace = manager.evaluate_exit_strategy(
            position_retrace, 100000.0, 55.0,
            high_water_mark_pct=15.0  # Pass in tracked peak
        )
        
        # Should trigger full exit
        assert decision_retrace.should_sell
        assert decision_retrace.quantity == position_retrace.quantity
        assert decision_retrace.mode == "profit_lock"
    
    def test_profit_lock_overrides_scale_out(self, default_strategy_config):
        """Profit lock should take precedence over scale-out."""
        config = default_strategy_config.copy()
        config["profit_lock_arm"] = 10.0
        config["profit_lock_trail"] = 3.0
        
        manager = CorePositionManager(config)
        
        # Position at 12%, then retraces to 8%
        position = MockPosition("ETHU", 100, 50.0, 54.0)  # 8%
        
        decision = manager.evaluate_exit_strategy(
            position, 100000.0, 54.0,
            high_water_mark_pct=12.0
        )
        
        # Should sell all (profit lock) not partial (scale-out)
        assert decision.should_sell
        assert decision.mode == "profit_lock"
        assert decision.quantity == position.quantity


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_zero_quantity_position(self, default_strategy_config):
        """Handle position with zero quantity."""
        manager = CorePositionManager(default_strategy_config)
        
        position = MockPosition("ETHU", 0, 50.0, 55.0)
        
        decision = manager.evaluate_exit_strategy(
            position, 100000.0, 55.0
        )
        
        assert not decision.should_sell
    
    def test_losing_position(self, default_strategy_config):
        """Handle position in loss."""
        manager = CorePositionManager(default_strategy_config)
        
        # Position at -10% loss
        position = MockPosition("ETHU", 100, 50.0, 45.0)
        
        decision = manager.evaluate_exit_strategy(
            position, 100000.0, 45.0
        )
        
        # Should not trigger any exit strategy
        assert not decision.should_sell
    
    def test_very_small_account(self, default_strategy_config):
        """Handle very small account value."""
        manager = CorePositionManager(default_strategy_config)
        
        # Tiny account
        position = MockPosition("ETHU", 10, 50.0, 55.0)
        
        decision = manager.evaluate_exit_strategy(
            position, 1000.0, 55.0
        )
        
        # Should still work, not crash
        assert decision is not None


class TestModeTransitions:
    """Test transitions between exit modes."""
    
    def test_rebalancing_to_scale_out(self, default_strategy_config):
        """Test transition from rebalancing to scale-out mode."""
        manager = CorePositionManager(default_strategy_config)
        
        # Start with large position (rebalancing)
        account_value = 100000.0
        
        # 18% position
        position_large = MockPosition("ETHU", 200, 45.0, 50.0)
        decision1 = manager.evaluate_exit_strategy(
            position_large, account_value, 50.0
        )
        assert decision1.mode == "rebalancing"
        
        # After sells, position drops to 14%
        position_reduced = MockPosition("ETHU", 150, 45.0, 51.0)
        decision2 = manager.evaluate_exit_strategy(
            position_reduced, account_value, 51.0
        )
        assert decision2.mode != "rebalancing"
    
    def test_scale_out_to_profit_lock(self, default_strategy_config):
        """Test transition from scale-out to profit lock."""
        config = default_strategy_config.copy()
        config["profit_lock_arm"] = 10.0
        
        manager = CorePositionManager(config)
        
        # Position at 8% (scale-out territory)
        position = MockPosition("ETHU", 100, 50.0, 54.0)
        decision1 = manager.evaluate_exit_strategy(
            position, 100000.0, 54.0
        )
        if decision1.should_sell:
            assert decision1.mode == "scale_out"
        
        # Position reaches 12%, then retraces
        position_retrace = MockPosition("ETHU", 100, 50.0, 54.5)
        decision2 = manager.evaluate_exit_strategy(
            position_retrace, 100000.0, 54.5,
            high_water_mark_pct=12.0
        )
        # Profit lock should now be active
        assert decision2.profit_lock_armed


class TestConfigurationVariations:
    """Test with different configuration parameters."""
    
    def test_aggressive_scale_out(self, default_strategy_config):
        """Test with aggressive scale-out parameters."""
        config = default_strategy_config.copy()
        config["scale_out_pct"] = 25.0  # Larger chunks
        config["scale_out_step"] = 2.0  # More frequent
        
        manager = CorePositionManager(config)
        
        # Should trigger at 4% (2 * step)
        position = MockPosition("ETHU", 100, 50.0, 52.0)
        decision = manager.evaluate_exit_strategy(
            position, 100000.0, 52.0
        )
        
        assert decision.should_sell
    
    def test_conservative_profit_lock(self, default_strategy_config):
        """Test with conservative (early) profit lock."""
        config = default_strategy_config.copy()
        config["profit_lock_arm"] = 6.0   # Arms early
        config["profit_lock_trail"] = 2.0  # Tight trail
        
        manager = CorePositionManager(config)
        
        # Should arm at 6%
        position = MockPosition("ETHU", 100, 50.0, 53.0)
        decision = manager.evaluate_exit_strategy(
            position, 100000.0, 53.0
        )
        
        assert decision.profit_lock_armed
