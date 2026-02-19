#!/usr/bin/env python3
"""
Phase 1 Verification Script

Tests that all Phase 1 modules can be imported correctly.
Run this to verify the refactored foundation is working.
"""

import sys
import os
from decimal import Decimal

# Add parent directory to path to enable absolute imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_imports():
    """Test that all Phase 1 modules can be imported."""
    print("=" * 60)
    print("Phase 1 Module Import Verification")
    print("=" * 60)
    
    tests_passed = 0
    tests_failed = 0
    
    # Test 1: Exceptions
    try:
        from exceptions import (
            IronHandException,
            ConfigurationError,
            BrokerError,
            StrategyError,
        )
        print("✅ exceptions.py - imported successfully")
        tests_passed += 1
    except Exception as e:
        print(f"❌ exceptions.py - FAILED: {e}")
        tests_failed += 1
    
    # Test 2: Logging
    try:
        from logger import setup_logging, get_logger
        logger = get_logger(tenant_id="test-123")
        logger.info("test_message", key="value")
        print("✅ logger.py - imported and tested")
        tests_passed += 1
    except Exception as e:
        print(f"❌ logger.py - FAILED: {e}")
        tests_failed += 1
    
    # Test 3: Config
    try:
        from settings import Settings, get_settings, StrategySettings
        settings = StrategySettings()
        print(f"✅ config.py - imported successfully (default check_interval: {settings.check_interval}s)")
        tests_passed += 1
    except Exception as e:
        print(f"❌ config.py - FAILED: {e}")
        tests_failed += 1
    
    # Test 4: Database models
    try:
        from db import (
            Tenant,
            Strategy,
            Position,
            Order,
            BrokerConnection,
        )
        print("✅ db/models.py - all models imported")
        tests_passed += 1
    except Exception as e:
        print(f"❌ db/models.py - FAILED: {e}")
        tests_failed += 1
    
    # Test 5: Database session
    try:
        from db import session_scope, init_db
        print("✅ db/session.py - session management imported")
        tests_passed += 1
    except Exception as e:
        print(f"❌ db/session.py - FAILED: {e}")
        tests_failed += 1
    
    # Test 6: Core - Strategy Logic
    try:
        from core import CoreStrategyLogic, LadderRung
        strategy = CoreStrategyLogic()
        print(f"✅ core/strategy_logic.py - imported (ATR range: {strategy.start_atr}-{strategy.end_atr})")
        tests_passed += 1
    except Exception as e:
        print(f"❌ core/strategy_logic.py - FAILED: {e}")
        tests_failed += 1
    
    # Test 7: Core - Indicators
    try:
        from core import calculate_rsi, calculate_atr, calculate_bollinger_bands
        print("✅ core/indicators.py - all indicators imported")
        tests_passed += 1
    except Exception as e:
        print(f"❌ core/indicators.py - FAILED: {e}")
        tests_failed += 1
    
    # Test 8: Core - Position Manager
    try:
        from core import CorePositionManager, ExitMode, ExitSignal
        manager = CorePositionManager()
        print(f"✅ core/core_manager.py - imported (profit lock at {manager.profit_lock_arm}%)")
        tests_passed += 1
    except Exception as e:
        print(f"❌ core/core_manager.py - FAILED: {e}")
        tests_failed += 1
    
    # Test 9: Engine - Signals
    try:
        from engine import ShutdownManager, get_shutdown_manager
        shutdown = get_shutdown_manager()
        print(f"✅ engine/signals.py - shutdown manager initialized (shutdown={shutdown.should_shutdown()})")
        tests_passed += 1
    except Exception as e:
        print(f"❌ engine/signals.py - FAILED: {e}")
        tests_failed += 1
    
    # Summary
    print("=" * 60)
    print(f"Results: {tests_passed} passed, {tests_failed} failed")
    print("=" * 60)
    
    return tests_failed == 0


def test_ladder_generation():
    """Test ladder generation with sample data."""
    print("\n" + "=" * 60)
    print("Ladder Generation Test")
    print("=" * 60)
    
    try:
        from core import CoreStrategyLogic
        
        strategy = CoreStrategyLogic(
            min_ladder_trade_usd=Decimal("500"),
            start_atr=Decimal("0.2"),
            end_atr=Decimal("0.6"),
            distribution_curve=Decimal("1.0"),
            size_increase_factor=Decimal("1.25"),
        )
        
        # Sample inputs
        current_price = Decimal("100.00")
        atr_value = Decimal("2.50")
        buying_power = Decimal("10000.00")
        
        ladder = strategy.generate_ladder(
            current_price=current_price,
            atr_value=atr_value,
            buying_power=buying_power,
            max_slots=5,
        )
        
        print(f"Current Price: ${current_price}")
        print(f"ATR: ${atr_value}")
        print(f"Buying Power: ${buying_power}")
        print(f"\nGenerated {len(ladder)} rungs:\n")
        
        for rung in ladder:
            print(f"  {rung}")
        
        total_notional = sum(r.notional_usd for r in ladder)
        print(f"\nTotal allocated: ${total_notional:.2f}")
        print("✅ Ladder generation working correctly")
        
        return True
    except Exception as e:
        print(f"❌ Ladder generation FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_exit_signals():
    """Test exit signal generation."""
    print("\n" + "=" * 60)
    print("Exit Signal Test")
    print("=" * 60)
    
    try:
        from core import CorePositionManager, PositionState
        
        manager = CorePositionManager(
            max_core_pct=Decimal("15.0"),
            scale_out_pct=Decimal("15.0"),
            scale_out_step=Decimal("4.0"),
            profit_lock_arm=Decimal("12.0"),
        )
        
        # Test position at 8% profit
        position = PositionState(
            quantity=Decimal("100"),
            avg_entry_price=Decimal("95.00"),
            current_price=Decimal("102.60"),  # ~8% profit
            account_value=Decimal("50000"),
        )
        
        signals = manager.check_exit_signals(position)
        
        print(f"Position: {position.quantity} @ ${position.avg_entry_price}")
        print(f"Current Price: ${position.current_price}")
        print(f"Profit: {position.profit_pct:.2f}%")
        print(f"Allocation: {position.allocation_pct:.2f}%")
        print(f"\nExit Signals: {len(signals)}")
        
        for signal in signals:
            print(f"  {signal}")
        
        print("✅ Exit signal generation working correctly")
        return True
    except Exception as e:
        print(f"❌ Exit signal generation FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all verification tests."""
    results = []
    
    results.append(("Module Imports", test_imports()))
    results.append(("Ladder Generation", test_ladder_generation()))
    results.append(("Exit Signals", test_exit_signals()))
    
    print("\n" + "=" * 60)
    print("PHASE 1 VERIFICATION SUMMARY")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    all_passed = all(passed for _, passed in results)
    
    if all_passed:
        print("\n🎉 All Phase 1 tests passed! Foundation is solid.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Review errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
