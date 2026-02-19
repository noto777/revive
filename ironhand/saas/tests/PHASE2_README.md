# Phase 2 Test Suite

**Author:** IronHand Tester Agent  
**Date:** 2026-02-14  
**Status:** ✅ Complete and ready for validation

---

## Overview

This directory contains comprehensive test coverage for IronHand SaaS Phase 2 modules:

- **Broker abstraction** (Alpaca, Paper, error handling)
- **Event bus** (pub/sub, async, multi-tenant)
- **Notifications** (Telegram, Webhook, dispatcher routing)
- **Database migrations** (Alembic, schema validation)

**Total:** 105 test cases, ~2,900 lines of test code

---

## Quick Start

### Install Dependencies

```bash
pip install -r requirements-test.txt
```

### Run All Phase 2 Tests

```bash
pytest tests/test_brokers.py tests/test_events.py tests/test_notifications.py tests/test_migrations.py -v
```

### Run Specific Module

```bash
# Broker tests only
pytest tests/test_brokers.py -v

# Event bus tests only
pytest tests/test_events.py -v

# Notifications tests only
pytest tests/test_notifications.py -v

# Migration tests only
pytest tests/test_migrations.py -v
```

### Run with Coverage

```bash
pytest tests/ --cov=ironhand --cov-report=html --cov-report=term
```

---

## Test Files

### 1. `test_brokers.py` (29 tests)

Tests the broker abstraction layer and implementations.

**Key test classes:**
- `TestBrokerInterfaceCompliance` — Validates all brokers implement `BrokerInterface`
- `TestAlpacaBroker` — Alpaca SDK integration (mocked)
- `TestPaperBroker` — Paper trading simulation
- `TestBrokerErrorHandling` — Connection failures, retries, timeouts
- `TestBrokerIntegration` — End-to-end workflows

**Run:**
```bash
pytest tests/test_brokers.py -v
```

---

### 2. `test_events.py` (25 tests)

Tests the internal event bus for async pub/sub.

**Key test classes:**
- `TestEventBus` — Core pub/sub mechanism
- `TestEventTypes` — Event type structure validation
- `TestOrderFilledEvent` — Specific event type tests
- `TestEventBusAsync` — Async/await compatibility
- `TestEventBusPerformance` — Throughput validation

**Run:**
```bash
pytest tests/test_events.py -v
```

---

### 3. `test_notifications.py` (27 tests)

Tests notification routing and channel implementations.

**Key test classes:**
- `TestNotificationDispatcher` — Event routing to channels
- `TestTelegramNotifier` — Message formatting, retry logic
- `TestWebhookNotifier` — JSON payloads, HMAC signatures
- `TestChannelFiltering` — Subscription-based filtering
- `TestNotificationIntegration` — End-to-end flow

**Run:**
```bash
pytest tests/test_notifications.py -v
```

---

### 4. `test_migrations.py` (24 tests)

Tests Alembic migrations and schema validation.

**Key test classes:**
- `TestAlembicConfig` — Config validation
- `TestMigrationScripts` — Upgrade/downgrade, idempotency
- `TestSchemaMatchesModels` — Schema drift detection
- `TestDataPreservation` — Data safety during migrations
- `TestDatabaseCompatibility` — Postgres vs SQLite

**Run:**
```bash
pytest tests/test_migrations.py -v
```

---

## Test Conventions

### Skip Decorators

Tests use `@pytest.mark.skip("Waiting for X implementation")` until modules are built.

**To enable tests:**
1. Remove skip decorator from test
2. Uncomment imports at top of file
3. Run test

Example:
```python
# Before:
@pytest.mark.skip("Waiting for brokers.alpaca implementation")
async def test_connect_success(self, alpaca_broker):
    ...

# After implementation:
async def test_connect_success(self, alpaca_broker):
    ...
```

### Mocking Strategy

- **External APIs mocked** (Alpaca SDK, Telegram API, webhooks)
- **Internal logic tested** (routing, validation, error handling)
- **Database isolated** (temp SQLite for each test)

### Async Tests

All broker, event, and notification tests are async (`@pytest.mark.asyncio`).

```python
pytestmark = pytest.mark.asyncio  # Top of file

async def test_example(self):  # Note: async def
    result = await some_async_function()
    assert result is not None
```

---

## Common Test Patterns

### Testing Broker Methods

```python
@pytest.fixture
async def mock_alpaca_client(self):
    """Mock Alpaca SDK client."""
    with patch('ironhand.brokers.alpaca.tradeapi') as mock_api:
        client = MagicMock()
        mock_api.REST.return_value = client
        yield client

async def test_place_order(self, alpaca_broker, mock_alpaca_client):
    mock_alpaca_client.submit_order.return_value = MagicMock(id="order_123")
    
    order_id = await alpaca_broker.place_order(request)
    
    assert order_id == "order_123"
    mock_alpaca_client.submit_order.assert_called_once()
```

### Testing Event Bus

```python
async def test_publish_subscribe(self, event_bus):
    received_events = []
    
    async def subscriber(event: Event):
        received_events.append(event)
    
    event_bus.subscribe(EventType.ORDER_FILLED, subscriber)
    await event_bus.publish(Event(type=EventType.ORDER_FILLED, data={}))
    
    await asyncio.sleep(0.1)  # Let async tasks complete
    assert len(received_events) == 1
```

### Testing Migrations

```python
def test_upgrade_head(self, alembic_config, temp_db_engine):
    command.upgrade(alembic_config, "head")
    
    inspector = inspect(temp_db_engine)
    tables = inspector.get_table_names()
    
    assert "tenants" in tables
    assert "strategies" in tables
```

---

## Fixtures

All fixtures are defined in `conftest.py`:

### Database Fixtures
- `test_db_path` — Temp SQLite file
- `db_session` — Fresh session per test
- `migrated_engine` — DB with migrations applied
- `model_engine` — DB from models directly

### Sample Data Fixtures
- `sample_tenant` — Test tenant
- `sample_strategy` — Test strategy
- `sample_strategy_config` — Default config
- `sample_position` — Open position
- `sample_order` — Pending order
- `sample_market_data` — OHLCV DataFrame

### Edge Case Fixtures
- `zero_atr_market_data` — No volatility
- `negative_price_data` — Invalid prices
- `empty_market_data` — Empty DataFrame

### Mock Fixtures (per test file)
- `mock_alpaca_client` — Mocked Alpaca SDK
- `mock_telegram` — Mocked Telegram notifier
- `mock_webhook` — Mocked webhook client

---

## Troubleshooting

### Issue: Tests are all skipped

**Cause:** Implementation not ready yet  
**Solution:** Wait for implementation, then remove `@pytest.mark.skip` decorators

### Issue: ImportError when uncommenting imports

**Cause:** Module not implemented yet  
**Solution:** Implement the module first, then enable tests

### Issue: Alembic migration tests fail

**Cause:** `alembic.ini` not created  
**Solution:** Run `alembic init migrations` to set up Alembic

### Issue: Tests hang on async operations

**Cause:** Missing `await` or event loop issue  
**Solution:** Ensure all async functions are awaited, check pytest-asyncio config

---

## Test Quality Checklist

When writing new tests:

- [ ] Test has clear docstring
- [ ] Uses appropriate fixtures
- [ ] Mocks external dependencies
- [ ] Has meaningful assertions
- [ ] Tests edge cases (empty, null, invalid)
- [ ] Tests error paths (exceptions)
- [ ] Cleans up resources (temp files, connections)
- [ ] Is isolated (doesn't depend on other tests)
- [ ] Runs fast (<1 second per test)

---

## Coverage Goals

| Module | Target Coverage | Current Status |
|--------|----------------|----------------|
| `brokers/` | 90%+ | Tests ready ⏳ |
| `engine/events.py` | 95%+ | Tests ready ⏳ |
| `notifications/` | 90%+ | Tests ready ⏳ |
| `db/migrations/` | 85%+ | Tests ready ⏳ |

**Note:** "Tests ready" means test suite is written; coverage will be measured once implementation lands.

---

## Next Steps

1. ✅ Phase 2 tests written
2. ⏳ Wait for implementation
3. ⏳ Remove skip decorators as modules land
4. ⏳ Run tests, report failures
5. ⏳ Iterate until all pass
6. ⏳ Generate coverage report
7. ⏳ Report to team lead

---

## Contact

**Questions about tests?** Ping `ironhand-tester` session

**Found a bug in tests?** Create issue or ping tester directly

**Need test coverage for new feature?** Request via `ironhand-lead`

---

**Status:** ✅ Ready for implementation validation
