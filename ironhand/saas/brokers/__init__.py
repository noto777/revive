"""
Broker Abstraction Layer

Provides a unified interface for different broker integrations.
Supports Alpaca (primary SaaS broker), IBKR (live bot only), and paper trading.
"""

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
from .alpaca import AlpacaBroker
from .paper import PaperBroker

__all__ = [
    # Base types
    "BrokerInterface",
    "AccountSummary",
    "Execution",
    "Order",
    "OrderRequest",
    "Position",
    # Enums
    "OrderSide",
    "OrderStatus",
    "OrderType",
    "PositionSide",
    # Implementations
    "AlpacaBroker",
    "PaperBroker",
]
