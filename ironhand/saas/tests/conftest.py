"""
Pytest fixtures for IronHand SaaS test suite.

Provides:
- Test database with tenant isolation
- Mock broker implementations
- Sample market data (OHLCV)
- Strategy configurations
- WebSocket test clients
"""

import asyncio
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from decimal import Decimal
from typing import AsyncGenerator, Generator
from uuid import uuid4

# These imports will exist once implementation is done
# For now, we're testing against the architecture spec
try:
    from ironhand.db.models import (
        Base, Tenant, BrokerConnection, Strategy, Position, Order, Execution
    )
    from ironhand.db.session import get_session_factory, create_test_db
    from ironhand.brokers.base import BrokerInterface
    from ironhand.core.strategy_logic import CoreStrategyLogic
    from ironhand.core.core_manager import CorePositionManager
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
except ImportError:
    # Stub for parallel development
    Base = None
    Tenant = None
    Strategy = None
    AsyncSession = None
    BrokerInterface = None
    CoreStrategyLogic = None
    CorePositionManager = None
    get_session_factory = None
    create_test_db = None


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def test_db_engine():
    """Create a fresh test database for each test."""
    from sqlalchemy.ext.asyncio import create_async_engine
    
    # In-memory SQLite for fast tests
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True
    )
    
    # Create all tables
    if Base:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    await engine.dispose()


@pytest.fixture
async def db_session(test_db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session for a single test."""
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker
    
    async_session = sessionmaker(
        test_db_engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def tenant(db_session) -> Tenant:
    """Create a test tenant."""
    tenant = Tenant(
        id=uuid4(),
        name="Test User",
        email="test@example.com",
        plan="pro",
        max_strategies=5,
        is_active=True
    )
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)
    return tenant


@pytest.fixture
async def second_tenant(db_session) -> Tenant:
    """Create a second tenant for isolation tests."""
    tenant = Tenant(
        id=uuid4(),
        name="Second User",
        email="second@example.com",
        plan="free",
        max_strategies=1,
        is_active=True
    )
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)
    return tenant


# ============================================================================
# Broker Fixtures
# ============================================================================

class MockBroker(BrokerInterface if BrokerInterface else object):
    """Mock broker for testing without IBKR connection."""
    
    def __init__(self):
        self.connected = False
        self.positions = []
        self.orders = []
        self.fills_callback = None
        self.account_value = 100000.0
        self.market_data = {}
        
    async def connect(self) -> None:
        self.connected = True
        
    async def disconnect(self) -> None:
        self.connected = False
        
    async def get_positions(self):
        return self.positions
        
    async def get_account_summary(self):
        return {
            "net_liquidation": self.account_value,
            "cash": self.account_value * 0.3,
            "buying_power": self.account_value * 0.5
        }
        
    async def place_order(self, order):
        order_id = f"MOCK_{len(self.orders)}"
        self.orders.append({
            "id": order_id,
            "symbol": order.symbol,
            "side": order.side,
            "quantity": order.quantity,
            "order_type": order.order_type,
            "limit_price": order.limit_price,
            "status": "pending"
        })
        return order_id
        
    async def cancel_order(self, broker_order_id: str) -> None:
        for order in self.orders:
            if order["id"] == broker_order_id:
                order["status"] = "cancelled"
                
    async def get_market_data(self, symbol: str, duration: str = "1 D"):
        if symbol in self.market_data:
            return self.market_data[symbol]
        # Return synthetic data if not mocked
        return generate_sample_ohlcv(symbol)
        
    def on_fill(self, callback):
        self.fills_callback = callback
        
    def simulate_fill(self, order_id: str, fill_price: float, quantity: float):
        """Test helper to simulate order fills."""
        if self.fills_callback:
            self.fills_callback({
                "order_id": order_id,
                "price": fill_price,
                "quantity": quantity,
                "timestamp": datetime.utcnow()
            })


@pytest.fixture
def mock_broker():
    """Provide a mock broker instance."""
    return MockBroker()


@pytest.fixture
def paper_broker():
    """Provide a paper trading broker (more realistic than mock)."""
    # This would return the actual PaperBroker once implemented
    return MockBroker()  # Use mock for now


# ============================================================================
# Market Data Fixtures
# ============================================================================

def generate_sample_ohlcv(
    symbol: str = "ETHU",
    periods: int = 100,
    start_price: float = 50.0,
    volatility: float = 0.02
) -> pd.DataFrame:
    """Generate synthetic OHLCV data for testing."""
    
    np.random.seed(42)  # Reproducible tests
    
    dates = pd.date_range(
        end=datetime.utcnow(),
        periods=periods,
        freq='5min'
    )
    
    # Random walk with drift
    returns = np.random.normal(0.0001, volatility, periods)
    prices = start_price * np.exp(np.cumsum(returns))
    
    # OHLC construction
    highs = prices * (1 + np.abs(np.random.normal(0, 0.005, periods)))
    lows = prices * (1 - np.abs(np.random.normal(0, 0.005, periods)))
    opens = prices * (1 + np.random.normal(0, 0.003, periods))
    
    volumes = np.random.randint(10000, 100000, periods)
    
    df = pd.DataFrame({
        'open': opens,
        'high': highs,
        'low': lows,
        'close': prices,
        'volume': volumes
    }, index=dates)
    
    return df


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """Provide sample OHLCV data."""
    return generate_sample_ohlcv()


@pytest.fixture
def ohlcv_with_trend() -> pd.DataFrame:
    """OHLCV data with clear upward trend."""
    df = generate_sample_ohlcv(periods=200, volatility=0.015)
    # Add upward drift
    trend = np.linspace(0, 0.2, len(df))
    df['close'] = df['close'] * (1 + trend)
    df['high'] = df['high'] * (1 + trend)
    df['low'] = df['low'] * (1 + trend)
    df['open'] = df['open'] * (1 + trend)
    return df


@pytest.fixture
def ohlcv_oversold() -> pd.DataFrame:
    """OHLCV data where RSI is clearly oversold (<30)."""
    df = generate_sample_ohlcv(periods=100, start_price=60.0)
    # Force downward movement
    downtrend = np.linspace(0, -0.15, len(df))
    df['close'] = df['close'] * (1 + downtrend)
    return df


# ============================================================================
# Strategy Configuration Fixtures
# ============================================================================

@pytest.fixture
def default_strategy_config():
    """Default strategy configuration matching ARCHITECTURE.md spec."""
    return {
        "check_interval": 15,
        "min_ladder_trade_usd": 500,
        "start_atr": 0.2,
        "end_atr": 0.6,
        "distribution_curve": 1.0,
        "size_increase_factor": 1.25,
        "max_core_pct": 15.0,
        "core_hysteresis_gap": 2.0,
        "scale_out_pct": 15.0,
        "scale_out_step": 4.0,
        "profit_lock_arm": 12.0,
        "profit_lock_trail": 4.0
    }


@pytest.fixture
def aggressive_strategy_config(default_strategy_config):
    """Aggressive strategy config (wider ladder spread)."""
    config = default_strategy_config.copy()
    config.update({
        "start_atr": 0.3,
        "end_atr": 0.8,
        "size_increase_factor": 1.5
    })
    return config


@pytest.fixture
async def strategy(db_session, tenant, default_strategy_config):
    """Create a test strategy instance."""
    if not Strategy:
        pytest.skip("Strategy model not implemented yet")
        
    strategy = Strategy(
        id=uuid4(),
        tenant_id=tenant.id,
        symbol="ETHU",
        status="stopped",
        config=default_strategy_config
    )
    db_session.add(strategy)
    await db_session.commit()
    await db_session.refresh(strategy)
    return strategy


# ============================================================================
# Position & Order Fixtures
# ============================================================================

@pytest.fixture
async def open_position(db_session, strategy, tenant):
    """Create an open position."""
    if not Position:
        pytest.skip("Position model not implemented yet")
        
    position = Position(
        id=uuid4(),
        strategy_id=strategy.id,
        tenant_id=tenant.id,
        symbol="ETHU",
        entry_price=Decimal("50.25"),
        quantity=Decimal("100"),
        side="LONG",
        status="open",
        rung_index=2
    )
    db_session.add(position)
    await db_session.commit()
    await db_session.refresh(position)
    return position


# ============================================================================
# Helpers
# ============================================================================

@pytest.fixture
def assert_decimal():
    """Helper for comparing Decimal values with tolerance."""
    def _assert(actual: Decimal, expected: Decimal, tolerance: float = 0.01):
        diff = abs(float(actual) - float(expected))
        assert diff <= tolerance, f"Expected {expected}, got {actual} (diff: {diff})"
    return _assert


@pytest.fixture
def assert_approx():
    """Helper for comparing floats with tolerance."""
    def _assert(actual: float, expected: float, tolerance: float = 0.01):
        diff = abs(actual - expected)
        assert diff <= tolerance, f"Expected {expected}, got {actual} (diff: {diff})"
    return _assert


# ============================================================================
# Fixture Aliases (for backward compatibility with test files)
# ============================================================================

@pytest.fixture
def sample_strategy_config(default_strategy_config):
    """Alias for default_strategy_config."""
    return default_strategy_config


@pytest.fixture
async def sample_tenant(tenant):
    """Alias for tenant."""
    return tenant


@pytest.fixture
async def sample_strategy(strategy):
    """Alias for strategy."""
    return strategy


def assert_no_regime_references(data):
    """Assert no regime-related keys exist in a config dict."""
    regime_keys = {'regime', 'aggressive_params', 'neutral_params', 'defensive_params',
                   'regime_mode', 'regime_filter', 'regime_type'}
    if isinstance(data, dict):
        for key in data:
            assert key.lower() not in regime_keys, f"Found regime reference: {key}"
            if isinstance(data[key], dict):
                assert_no_regime_references(data[key])
