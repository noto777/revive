"""
Paper Trading Broker Implementation

Simulates order execution for testing without real money.
Generates synthetic market data and executes orders with realistic fills.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Callable, Optional

import numpy as np
import pandas as pd
import structlog

from .base import (
    AccountSummary,
    BrokerInterface,
    Execution,
    Order,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    PositionSide,
)

logger = structlog.get_logger()


class PaperBroker(BrokerInterface):
    """
    Paper trading broker for testing.
    
    Simulates a broker with:
    - Synthetic price generation (random walk)
    - Instant order fills at market price
    - Position tracking
    - No commissions
    
    Args:
        initial_cash: Starting cash balance
        fill_delay_seconds: Simulated delay before fills (0 = instant)
    """
    
    def __init__(
        self,
        initial_cash: Decimal = Decimal("100000.00"),
        fill_delay_seconds: float = 0.1
    ):
        self.initial_cash = initial_cash
        self.fill_delay_seconds = fill_delay_seconds
        
        # State
        self._connected = False
        self._cash = initial_cash
        self._positions: dict[str, Position] = {}
        self._orders: dict[str, Order] = {}
        self._executions: list[Execution] = []
        self._fill_callbacks: list[Callable[[Execution], None]] = []
        
        # Price simulation
        self._prices: dict[str, Decimal] = {}
        self._price_base = Decimal("100.00")  # Base price for new symbols
        
        self.logger = logger.bind(broker="paper")
    
    async def connect(self) -> None:
        """Establish connection (simulated)."""
        if self._connected:
            self.logger.warning("Already connected")
            return
        
        self._connected = True
        self._cash = self.initial_cash
        self._positions.clear()
        self._orders.clear()
        self._executions.clear()
        
        self.logger.info("Paper broker connected", initial_cash=float(self.initial_cash))
    
    async def disconnect(self) -> None:
        """Close connection."""
        if not self._connected:
            return
        
        self._connected = False
        self._fill_callbacks.clear()
        
        self.logger.info("Paper broker disconnected")
    
    async def is_connected(self) -> bool:
        """Check connection status."""
        return self._connected
    
    async def get_positions(self) -> list[Position]:
        """Get all positions."""
        self._ensure_connected()
        return list(self._positions.values())
    
    async def get_account_summary(self) -> AccountSummary:
        """Get account summary."""
        self._ensure_connected()
        
        # Calculate portfolio value
        portfolio_value = self._cash
        for pos in self._positions.values():
            portfolio_value += pos.market_value
        
        return AccountSummary(
            account_id="PAPER001",
            equity=portfolio_value,
            cash=self._cash,
            buying_power=self._cash * Decimal("4"),  # Simulated margin
            portfolio_value=portfolio_value,
            currency="USD"
        )
    
    async def place_order(self, order: OrderRequest) -> str:
        """Place an order (simulated fill)."""
        self._ensure_connected()
        
        # Generate order ID
        order_id = str(uuid.uuid4())
        
        # Get or generate price
        price = await self.get_current_price(order.symbol)
        
        # Create order record
        db_order = Order(
            broker_order_id=order_id,
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            quantity=order.quantity,
            limit_price=order.limit_price,
            stop_price=order.stop_price,
            status=OrderStatus.PENDING,
            filled_quantity=Decimal("0"),
            average_fill_price=None,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        self._orders[order_id] = db_order
        
        # Simulate fill asynchronously
        asyncio.create_task(self._simulate_fill(order_id))
        
        self.logger.info(
            "Paper order placed",
            order_id=order_id,
            symbol=order.symbol,
            side=order.side.value,
            quantity=float(order.quantity)
        )
        
        return order_id
    
    async def cancel_order(self, broker_order_id: str) -> None:
        """Cancel an order."""
        self._ensure_connected()
        
        if broker_order_id not in self._orders:
            raise ValueError(f"Order {broker_order_id} not found")
        
        order = self._orders[broker_order_id]
        
        if order.status in (OrderStatus.FILLED, OrderStatus.CANCELLED):
            raise ValueError(f"Cannot cancel order in status {order.status}")
        
        order.status = OrderStatus.CANCELLED
        order.updated_at = datetime.now()
        
        self.logger.info("Paper order cancelled", order_id=broker_order_id)
    
    async def get_order(self, broker_order_id: str) -> Order:
        """Get order details."""
        self._ensure_connected()
        
        if broker_order_id not in self._orders:
            raise ValueError(f"Order {broker_order_id} not found")
        
        return self._orders[broker_order_id]
    
    async def get_market_data(
        self,
        symbol: str,
        duration: str = "1D",
        bar_size: str = "5min"
    ) -> pd.DataFrame:
        """Generate synthetic market data."""
        self._ensure_connected()
        
        # Parse duration
        duration_map = {
            "1D": 1,
            "5D": 5,
            "1W": 7,
            "1M": 30,
            "3M": 90,
        }
        days = duration_map.get(duration, 1)
        
        # Parse bar size (in minutes)
        bar_minutes_map = {
            "1min": 1,
            "5min": 5,
            "15min": 15,
            "1hour": 60,
            "1day": 1440,
        }
        bar_minutes = bar_minutes_map.get(bar_size, 5)
        
        # Calculate number of bars
        total_minutes = days * 24 * 60
        num_bars = total_minutes // bar_minutes
        
        # Generate timestamps
        end_time = datetime.now()
        start_time = end_time - timedelta(minutes=total_minutes)
        timestamps = pd.date_range(start=start_time, end=end_time, periods=num_bars)
        
        # Generate synthetic OHLCV (random walk)
        base_price = float(self._price_base)
        returns = np.random.normal(0, 0.01, num_bars)  # 1% volatility
        closes = base_price * np.exp(np.cumsum(returns))
        
        # Generate OHLC from closes
        opens = np.roll(closes, 1)
        opens[0] = base_price
        
        highs = np.maximum(opens, closes) * (1 + np.abs(np.random.normal(0, 0.005, num_bars)))
        lows = np.minimum(opens, closes) * (1 - np.abs(np.random.normal(0, 0.005, num_bars)))
        volumes = np.random.randint(100000, 1000000, num_bars)
        
        # Create DataFrame
        df = pd.DataFrame({
            'timestamp': timestamps,
            'open': opens,
            'high': highs,
            'low': lows,
            'close': closes,
            'volume': volumes
        })
        
        # Update current price for this symbol
        self._prices[symbol] = Decimal(str(closes[-1]))
        
        return df
    
    async def get_current_price(self, symbol: str) -> Decimal:
        """Get current price (or generate one)."""
        self._ensure_connected()
        
        if symbol not in self._prices:
            # Generate initial price
            self._prices[symbol] = self._price_base
        
        # Add small random movement
        movement = Decimal(str(np.random.normal(0, 0.001)))  # 0.1% volatility
        self._prices[symbol] *= (Decimal("1") + movement)
        
        return self._prices[symbol]
    
    def on_fill(self, callback: Callable[[Execution], None]) -> None:
        """Register fill callback."""
        self._fill_callbacks.append(callback)
        self.logger.info("Fill callback registered")
    
    def _ensure_connected(self):
        """Raise error if not connected."""
        if not self._connected:
            raise ConnectionError("Not connected to paper broker. Call connect() first.")
    
    async def _simulate_fill(self, order_id: str):
        """Simulate order execution after delay."""
        # Wait for simulated delay
        await asyncio.sleep(self.fill_delay_seconds)
        
        order = self._orders.get(order_id)
        if not order or order.status == OrderStatus.CANCELLED:
            return
        
        # Get fill price
        fill_price = await self.get_current_price(order.symbol)
        
        # For limit orders, only fill if price is favorable
        if order.order_type == OrderType.LIMIT:
            if order.side == OrderSide.BUY and fill_price > order.limit_price:
                return  # Price too high, don't fill
            if order.side == OrderSide.SELL and fill_price < order.limit_price:
                return  # Price too low, don't fill
            fill_price = order.limit_price  # Fill at limit price
        
        # Update order status
        order.status = OrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.average_fill_price = fill_price
        order.updated_at = datetime.now()
        
        # Create execution
        exec_id = str(uuid.uuid4())
        execution = Execution(
            broker_exec_id=exec_id,
            broker_order_id=order_id,
            symbol=order.symbol,
            side=order.side,
            price=fill_price,
            quantity=order.quantity,
            commission=Decimal("0"),  # No commission in paper trading
            executed_at=datetime.now()
        )
        
        self._executions.append(execution)
        
        # Update cash and positions
        trade_value = fill_price * order.quantity
        
        if order.side == OrderSide.BUY:
            self._cash -= trade_value
            self._update_position(order.symbol, order.quantity, fill_price, PositionSide.LONG)
        else:
            self._cash += trade_value
            self._update_position(order.symbol, -order.quantity, fill_price, PositionSide.SHORT)
        
        # Trigger callbacks
        for callback in self._fill_callbacks:
            try:
                callback(execution)
            except Exception as e:
                self.logger.error("Fill callback error", error=str(e))
        
        self.logger.info(
            "Paper order filled",
            order_id=order_id,
            symbol=order.symbol,
            side=order.side.value,
            quantity=float(order.quantity),
            price=float(fill_price)
        )
    
    def _update_position(
        self,
        symbol: str,
        quantity: Decimal,
        price: Decimal,
        side: PositionSide
    ):
        """Update position after trade."""
        if symbol in self._positions:
            pos = self._positions[symbol]
            
            # Update position
            new_qty = pos.quantity + quantity
            
            if new_qty == 0:
                # Position closed
                del self._positions[symbol]
            elif new_qty > 0:
                # Update average entry
                total_value = (pos.average_entry_price * pos.quantity) + (price * quantity)
                pos.quantity = new_qty
                pos.average_entry_price = total_value / new_qty
                pos.current_price = price
                pos.market_value = new_qty * price
                pos.unrealized_pnl = (price - pos.average_entry_price) * new_qty
            else:
                # Reversed position
                pos.quantity = abs(new_qty)
                pos.side = PositionSide.SHORT if side == PositionSide.SHORT else PositionSide.LONG
                pos.average_entry_price = price
                pos.current_price = price
                pos.market_value = abs(new_qty) * price
                pos.unrealized_pnl = Decimal("0")
        else:
            # New position
            self._positions[symbol] = Position(
                symbol=symbol,
                side=side,
                quantity=abs(quantity),
                average_entry_price=price,
                market_value=abs(quantity) * price,
                unrealized_pnl=Decimal("0"),
                current_price=price
            )
