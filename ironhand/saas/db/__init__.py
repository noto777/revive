"""
Database package for IronHand SaaS.

Unified database layer using SQLAlchemy.
Replaces the duplicate sqlite_manager.py and consolidates db_manager.py.
"""

from .models import (
    Base,
    BrokerConnection,
    Execution,
    NotificationChannel,
    Order,
    Position,
    Strategy,
    StrategySnapshot,
    Tenant,
)
from .session import (
    create_tables,
    drop_tables,
    get_session,
    init_db,
    session_scope,
)

__all__ = [
    # Models
    "Base",
    "Tenant",
    "BrokerConnection",
    "Strategy",
    "Position",
    "Order",
    "Execution",
    "NotificationChannel",
    "StrategySnapshot",
    # Session management
    "init_db",
    "get_session",
    "session_scope",
    "create_tables",
    "drop_tables",
]
