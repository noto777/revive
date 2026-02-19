"""
Tests for core/strategy_logic.py - Ladder generation algorithm.

Tests the CoreStrategyLogic class which generates ATR-based buy ladders
with curved multipliers and look-ahead sizing.

Focuses on:
- Ladder generation with known ATR/price values
- Curved multiplier distribution
- Look-ahead sizing algorithm
- Edge cases (single rung, zero ATR, extreme values)
"""

import pytest
import numpy as np
from decimal import Decimal


# Import will work once implementation exists
try:
    from ironhand.core.strategy_logic import CoreStrategyLogic, LadderRung
except ImportError:
    CoreStrategyLogic = None
    LadderRung = None
    

pytestmark = pytest.mark.skipif(
    CoreStrategyLogic is None,
    reason="CoreStrategyLogic not implemented yet"
)


class TestLadderGeneration:
    """Test basic ladder generation with known inputs."""
    
    def test_ladder_basic_structure(self, default_strategy_config):
        """Verify ladder has correct structure and ordering."""
        logic = CoreStrategyLogic(default_strategy_config)
        
        current_price = 50.0
        atr = 2.0
        account_value = 100000.0
        
        ladder = logic.generate_ladder(current_price, atr, account_value)
        
        # Should return a list of rungs
        assert isinstance(ladder, list)
        assert len(ladder) > 0
        
        # Each rung should be properly structured
        for rung in ladder:
            assert hasattr(rung, 'price')
            assert hasattr(rung, 'quantity')
            assert hasattr(rung, 'atr_multiplier')
            assert rung.price > 0
            assert rung.quantity > 0
            
        # Rungs should be ordered by descending price
        prices = [r.price for r in ladder]
        assert prices == sorted(prices, reverse=True)
        
    def test_ladder_respects_min_trade_value(self, default_strategy_config):
        """All ladder rungs should meet minimum trade value."""
        logic = CoreStrategyLogic(default_strategy_config)
        
        min_trade_usd = default_strategy_config["min_ladder_trade_usd"]
        current_price = 50.0
        atr = 2.0
        account_value = 100000.0
        
        ladder = logic.generate_ladder(current_price, atr, account_value)
        
        for rung in ladder:
            trade_value = rung.price * rung.quantity
            assert trade_value >= min_trade_usd * 0.95, \
                f"Rung value ${trade_value:.2f} below minimum ${min_trade_usd}"
    
    def test_curved_multiplier_distribution(self, default_strategy_config):
        """Verify ATR multipliers follow curved distribution."""
        config = default_strategy_config.copy()
        config["distribution_curve"] = 2.0  # Quadratic curve
        
        logic = CoreStrategyLogic(config)
        
        ladder = logic.generate_ladder(
            current_price=50.0,
            atr=2.0,
            account_value=100000.0
        )
        
        multipliers = [r.atr_multiplier for r in ladder]
        
        # With curve > 1, spacing should be non-linear
        # Earlier rungs should be closer together than later ones
        if len(multipliers) >= 3:
            early_gap = multipliers[1] - multipliers[0]
            late_gap = multipliers[-1] - multipliers[-2]
            assert late_gap > early_gap, \
                "Curved distribution should have wider spacing at the end"
    
    def test_size_increase_factor(self, default_strategy_config):
        """Verify position sizes increase by the configured factor."""
        config = default_strategy_config.copy()
        config["size_increase_factor"] = 1.5
        
        logic = CoreStrategyLogic(config)
        
        ladder = logic.generate_ladder(
            current_price=50.0,
            atr=2.0,
            account_value=100000.0
        )
        
        if len(ladder) >= 2:
            # Notional values should increase
            values = [r.price * r.quantity for r in ladder]
            
            for i in range(len(values) - 1):
                ratio = values[i + 1] / values[i]
                # Should be approximately the size_increase_factor
                assert 1.4 < ratio < 1.6, \
                    f"Size ratio {ratio:.2f} doesn't match factor 1.5"


class TestLookAheadSizing:
    """Test the look-ahead sizing algorithm."""
    
    def test_optimal_slot_count(self, default_strategy_config):
        """Verify algorithm finds optimal number of slots."""
        logic = CoreStrategyLogic(default_strategy_config)
        
        # With large account, should be able to fit many slots
        ladder_large = logic.generate_ladder(
            current_price=50.0,
            atr=2.0,
            account_value=500000.0
        )
        
        # With small account, should have fewer slots
        ladder_small = logic.generate_ladder(
            current_price=50.0,
            atr=2.0,
            account_value=10000.0
        )
        
        assert len(ladder_large) > len(ladder_small), \
            "Larger account should support more ladder rungs"
    
    def test_single_slot_no_division_by_zero(self, default_strategy_config):
        """Verify single-slot case doesn't cause division by zero."""
        logic = CoreStrategyLogic(default_strategy_config)
        
        # Very small account should still produce valid ladder
        ladder = logic.generate_ladder(
            current_price=50.0,
            atr=2.0,
            account_value=1000.0  # Very small
        )
        
        # Should have at least one rung
        assert len(ladder) >= 1
        
        # Should not raise any exceptions
        assert ladder[0].quantity > 0
        assert ladder[0].price > 0


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_zero_atr(self, default_strategy_config):
        """Handle zero ATR gracefully."""
        logic = CoreStrategyLogic(default_strategy_config)
        
        # Zero ATR should either raise or return empty ladder
        try:
            ladder = logic.generate_ladder(
                current_price=50.0,
                atr=0.0,
                account_value=100000.0
            )
            # If it doesn't raise, should return empty or single-rung ladder
            assert len(ladder) <= 1
        except ValueError:
            # Raising ValueError is also acceptable
            pass
    
    def test_extremely_high_atr(self, default_strategy_config):
        """Handle very high ATR (volatile market)."""
        logic = CoreStrategyLogic(default_strategy_config)
        
        ladder = logic.generate_ladder(
            current_price=50.0,
            atr=20.0,  # 40% of price
            account_value=100000.0
        )
        
        # Should still produce valid ladder
        assert len(ladder) > 0
        
        # All prices should be positive
        for rung in ladder:
            assert rung.price > 0
    
    def test_very_low_price_instrument(self, default_strategy_config):
        """Test with penny-stock level prices."""
        logic = CoreStrategyLogic(default_strategy_config)
        
        ladder = logic.generate_ladder(
            current_price=0.50,  # 50 cents
            atr=0.05,
            account_value=100000.0
        )
        
        # Should still meet minimum trade value
        min_trade = default_strategy_config["min_ladder_trade_usd"]
        for rung in ladder:
            assert rung.price * rung.quantity >= min_trade * 0.95
    
    def test_negative_inputs_rejected(self, default_strategy_config):
        """Negative values should raise ValueError."""
        logic = CoreStrategyLogic(default_strategy_config)
        
        with pytest.raises(ValueError):
            logic.generate_ladder(
                current_price=-50.0,
                atr=2.0,
                account_value=100000.0
            )
        
        with pytest.raises(ValueError):
            logic.generate_ladder(
                current_price=50.0,
                atr=-2.0,
                account_value=100000.0
            )
        
        with pytest.raises(ValueError):
            logic.generate_ladder(
                current_price=50.0,
                atr=2.0,
                account_value=-100000.0
            )


class TestConfigurationVariations:
    """Test different configuration parameter combinations."""
    
    def test_tight_ladder_spread(self, default_strategy_config):
        """Test with tight ATR range."""
        config = default_strategy_config.copy()
        config["start_atr"] = 0.1
        config["end_atr"] = 0.2
        
        logic = CoreStrategyLogic(config)
        ladder = logic.generate_ladder(50.0, 2.0, 100000.0)
        
        # Rungs should be close together
        prices = [r.price for r in ladder]
        if len(prices) >= 2:
            max_gap = max(prices[i] - prices[i+1] for i in range(len(prices)-1))
            assert max_gap < 1.0, "Tight spread should have small price gaps"
    
    def test_wide_ladder_spread(self, default_strategy_config):
        """Test with wide ATR range."""
        config = default_strategy_config.copy()
        config["start_atr"] = 0.2
        config["end_atr"] = 1.0
        
        logic = CoreStrategyLogic(config)
        ladder = logic.generate_ladder(50.0, 2.0, 100000.0)
        
        # Should span wider price range
        if len(ladder) >= 2:
            total_span = ladder[0].price - ladder[-1].price
            assert total_span > 2.0, "Wide spread should cover more price range"
    
    def test_linear_vs_curved_distribution(self, default_strategy_config):
        """Compare linear and curved distributions."""
        config_linear = default_strategy_config.copy()
        config_linear["distribution_curve"] = 1.0
        
        config_curved = default_strategy_config.copy()
        config_curved["distribution_curve"] = 2.0
        
        logic_linear = CoreStrategyLogic(config_linear)
        logic_curved = CoreStrategyLogic(config_curved)
        
        ladder_linear = logic_linear.generate_ladder(50.0, 2.0, 100000.0)
        ladder_curved = logic_curved.generate_ladder(50.0, 2.0, 100000.0)
        
        # Both should have rungs
        assert len(ladder_linear) > 0
        assert len(ladder_curved) > 0
        
        # Curved should have different spacing pattern
        if len(ladder_linear) >= 3 and len(ladder_curved) >= 3:
            # Not strictly testing the difference, just that both are valid
            assert ladder_linear[0].price > ladder_linear[-1].price
            assert ladder_curved[0].price > ladder_curved[-1].price


class TestIntegrationScenarios:
    """Integration tests with realistic scenarios."""
    
    def test_typical_etf_scenario(self, default_strategy_config):
        """Test with typical leveraged ETF parameters."""
        logic = CoreStrategyLogic(default_strategy_config)
        
        # ETHU-like parameters
        ladder = logic.generate_ladder(
            current_price=52.50,
            atr=2.1,
            account_value=100000.0
        )
        
        assert len(ladder) >= 3, "Should create multiple rungs"
        
        # Total exposure shouldn't exceed reasonable limits
        total_value = sum(r.price * r.quantity for r in ladder)
        assert total_value < account_value * 0.5, \
            "Total ladder value shouldn't exceed 50% of account"
    
    def test_ladder_after_price_drop(self, default_strategy_config):
        """Test ladder generation after significant price drop."""
        logic = CoreStrategyLogic(default_strategy_config)
        
        # Price dropped 10% from previous level
        original_price = 50.0
        current_price = 45.0
        atr = 2.0
        
        ladder = logic.generate_ladder(current_price, atr, 100000.0)
        
        # Should generate valid ladder at new price
        assert len(ladder) > 0
        assert ladder[0].price <= current_price
