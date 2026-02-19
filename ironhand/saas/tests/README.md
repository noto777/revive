# IronHand SaaS Test Suite

Comprehensive test suite for the IronHand SaaS refactor project.

## Test Files

### Phase 1 Tests (Core Functionality)

- **conftest.py** — Shared fixtures and test utilities
- **test_models.py** — Database models (SQLAlchemy)
- **test_strategy_logic.py** — Ladder generation and sizing algorithms
- **test_core_manager.py** — Exit strategies (rebalancing, scale-out, profit lock)
- **test_indicators.py** — Technical indicators (RSI, BBands, ATR, WaveTrend)
- **test_config.py** — Pydantic configuration models
- **test_exceptions.py** — Exception hierarchy and structured logging

## Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_strategy_logic.py

# Run with coverage
pytest --cov=ironhand --cov-report=html

# Run only non-skipped tests (once implementation lands)
pytest -v

# Run specific test class
pytest tests/test_models.py::TestTenantModel

# Run specific test
pytest tests/test_strategy_logic.py::TestLadderGeneration::test_basic_ladder_generation
```

## Test Categories

### Critical Issue Verification (from ANALYSIS.md)

These tests verify the critical issues found in the live bot are fixed:

1. **No Duplicate DB Layer**
   - `test_models.py::TestDatabaseLayer::test_no_sqlite_manager_duplicate`
   - Verifies `sqlite_manager.py` has been deleted

2. **Regime System Removed**
   - `test_models.py::TestStrategyModel::test_strategy_no_regime_references`
   - `test_strategy_logic.py::TestLadderGeneration::test_no_regime_parameters`
   - `test_config.py::TestStrategyConfig::test_strategy_config_no_regime_fields`
   - Verifies no regime references in config or code

3. **Structured Logging Only**
   - `test_exceptions.py::TestStructuredLogging::test_no_print_statements_in_core`
   - Verifies no `print()` statements in core modules

4. **Division-by-Zero Fix**
   - `test_strategy_logic.py::TestLadderGeneration::test_single_slot_no_division_by_zero`
   - Verifies fix for single-slot ladder case

5. **Single RSI Implementation**
   - `test_indicators.py::TestRSI::test_rsi_single_implementation`
   - Verifies only one RSI calculation exists

## Edge Cases Tested

- Zero values (ATR, account value, quantity)
- Negative prices (should error)
- Empty data (empty DataFrames, no positions)
- Insufficient data (less than indicator period)
- NaN values in input
- Very large profits (>100%)
- Single-slot ladder generation

## Test Quality Standards

All tests should:

- ✅ Have descriptive names explaining what they test
- ✅ Test one thing at a time
- ✅ Include assertions with helpful failure messages
- ✅ Use fixtures for common setup
- ✅ Test both happy path and edge cases
- ✅ Be independent (no dependencies between tests)
- ✅ Be deterministic (same input = same output)

## Fixtures

### Database Fixtures
- `test_db_path` — Temporary SQLite database
- `db_session` — Fresh database session per test
- `sample_tenant` — Sample tenant record
- `sample_strategy` — Sample strategy with config
- `sample_position` — Sample open position
- `sample_order` — Sample order

### Market Data Fixtures
- `sample_market_data` — 100 bars of realistic OHLCV data
- `zero_atr_market_data` — Constant prices (no volatility)
- `negative_price_data` — Invalid negative prices
- `empty_market_data` — Empty DataFrame

### Configuration Fixtures
- `sample_strategy_config` — Standard strategy config (no regimes)

## Test Status

Current status: **SKELETONS READY** 🏗️

All test skeletons are written with:
- Clear test structure
- Edge cases identified
- Assertions planned
- Commented implementation code

Next step: **Fill in assertions as implementation lands** 🚀

## Communication

When tests fail or issues are found:

- Report test failures → `ironhand-impl` session
- Flag architectural deviations → `ironhand-architect` session
- Report phase completion → `ironhand-lead` session

## Coverage Goals

- **Phase 1**: 80%+ coverage of core modules
  - `core/strategy_logic.py` — 100%
  - `core/core_manager.py` — 100%
  - `core/indicators.py` — 95%+
  - `db/models.py` — 90%+
  - `config.py` — 100%

## Known Gaps (Future Phases)

Tests NOT yet covered (later phases):

- API endpoints (Phase 3)
- Authentication/authorization (Phase 3)
- WebSocket functionality (Phase 3)
- Multi-tenant isolation (Phase 4)
- Broker integrations (Phase 2)
- Executor lifecycle (Phase 2)
- Event bus (Phase 2)

---

**Tester:** IronHand SaaS Refactor Team  
**Last Updated:** 2026-02-14
