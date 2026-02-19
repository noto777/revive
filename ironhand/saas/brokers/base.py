"""
Abstract Broker Interface

Defines the contract that all broker implementations must follow.
Enables easy swapping between Alpaca, IBKR, paper trading, etc.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Callable, Optional

import pandas as pd


class OrderSide(str, Enum):
    """Order side (buy/sell)."""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """Order type."""
    MARKET = "MKT"
    LIMIT = "LMT"
    STOP = "STP"
    STOP_LIMIT = "STP_LMT"


class OrderStatus(str, Enum):
    """Order status."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    ERROR = "error"


class PositionSide(str, Enum):
    """Position side."""
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass
class OrderRequest:
    """Order submission request."""
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    limit_price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    time_in_force: str = "DAY"  # DAY, GTC, IOC, FOK
    
    def __post_init__(self):
        """Validate order request."""
        if self.order_type in (OrderType.LIMIT, OrderType.STOP_LIMIT) and self.limit_price is None:
            raise ValueError(f"{self.order_type} order requires limit_price")
        if self.order_type in (OrderType.STOP, OrderType.STOP_LIMIT) and self.stop_price is None:
            raise ValueError(f"{self.order_type} order requires stop_price")


@dataclass
class Order:
    """Order representation."""
    broker_order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    limit_price: Optional[Decimal]
    stop_price: Optional[Decimal]
    status: OrderStatus
    filled_quantity: Decimal = Decimal("0")
    average_fill_price: Optional[Decimal] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class Execution:
    """Order fill/execution."""
    broker_exec_id: str
    broker_order_id: str
    symbol: str
    side: OrderSide
    price: Decimal
    quantity: Decimal
    commission: Decimal
    executed_at: datetime


@dataclass
class Position:
    """Current position."""
    symbol: str
    side: PositionSide
    quantity: Decimal
    average_entry_price: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal
    current_price: Decimal


@dataclass
class AccountSummary:
    """Account summary information."""
    account_id: str
    equity: Decimal
    cash: Decimal
    buying_power: Decimal
    portfolio_value: Decimal
    currency: str = "USD"


class BrokerInterface(ABC):
    """
    Abstract broker interface.
    
    All broker implementations (Alpaca, IBKR, paper) must implement these methods.
    Designed to be async-compatible for the SaaS multi-tenant environment.
    """
    
    @abstractmethod
    async def connect(self) -> None:
        """
        Establish connection to the broker.
        
        Raises:
            ConnectionError: If connection fails
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """
        Close connection to the broker.
        Cleanup resources, cancel subscriptions, etc.
        """
        pass
    
    @abstractmethod
    async def is_connected(self) -> bool:
        """
        Check if broker connection is active.
        
        Returns:
            True if connected, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_positions(self) -> list[Position]:
        """
        Get all current positions.
        
        Returns:
            List of positions (empty if no positions)
        
        Raises:
            ConnectionError: If not connected
        """
        pass
    
    @abstractmethod
    async def get_account_summary(self) -> AccountSummary:
        """
        Get account summary (equity, cash, buying power).
        
        Returns:
            Account summary
        
        Raises:
            ConnectionError: If not connected
        """
        pass
    
    @abstractmethod
    async def place_order(self, order: OrderRequest) -> str:
        """
        Place an order.
        
        Args:
            order: Order request details
        
        Returns:
            Broker order ID
        
        Raises:
            ConnectionError: If not connected
            ValueError: If order parameters are invalid
        """
        pass
    
    @abstractmethod
    async def cancel_order(self, broker_order_id: str) -> None:
        """
        Cancel an open order.
        
        Args:
            broker_order_id: Broker's order ID
        
        Raises:
            ConnectionError: If not connected
            ValueError: If order not found or cannot be cancelled
        """
        pass
    
    @abstractmethod
    async def get_order(self, broker_order_id: str) -> Order:
        """
        Get order status and details.
        
        Args:
            broker_order_id: Broker's order ID
        
        Returns:
            Order details
        
        Raises:
            ConnectionError: If not connected
            ValueError: If order not found
        """
        pass
    
    @abstractmethod
    async def get_market_data(
        self,
        symbol: str,
        duration: str = "1D",
        bar_size: str = "5min"
    ) -> pd.DataFrame:
        """
        Get historical market data (OHLCV).
        
        Args:
            symbol: Ticker symbol
            duration: Duration string (e.g., "1D", "5D", "1M")
            bar_size: Bar size (e.g., "1min", "5min", "1hour", "1day")
        
        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        
        Raises:
            ConnectionError: If not connected
            ValueError: If symbol or parameters are invalid
        """
        pass
    
    @abstractmethod
    def on_fill(self, callback: Callable[[Execution], None]) -> None:
        """
        Register callback for order fills.
        
        Args:
            callback: Function to call when an order is filled
                     Signature: callback(execution: Execution) -> None
        """
        pass
    
    @abstractmethod
    async def get_current_price(self, symbol: str) -> Decimal:
        """
        Get current market price for a symbol.
        
        Args:
            symbol: Ticker symbol
        
        Returns:
            Current price
        
        Raises:
            ConnectionError: If not connected
            ValueError: If symbol is invalid
        """
        pass
