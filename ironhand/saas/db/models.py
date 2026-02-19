"""
SQLAlchemy Models for IronHand SaaS

PostgreSQL-ready with UUID primary keys, tenant isolation, and JSONB config.
Replaces the duplicate sqlite_manager.py and consolidates db_manager.py logic.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

# Use JSONB for PostgreSQL, fallback to JSON for SQLite
try:
    from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON
    JSONType = JSONB
except ImportError:
    JSONType = JSONB

Base = declarative_base()


class Tenant(Base):
    """
    Tenant (user account) for multi-tenant isolation.
    """
    __tablename__ = "tenants"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    api_key_hash = Column(String(255), nullable=True)
    plan = Column(String(20), default="free", nullable=False)  # free, pro, enterprise
    max_strategies = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    broker_connections = relationship("BrokerConnection", back_populates="tenant", cascade="all, delete-orphan")
    strategies = relationship("Strategy", back_populates="tenant", cascade="all, delete-orphan")
    notification_channels = relationship("NotificationChannel", back_populates="tenant", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Tenant {self.email} ({self.plan})>"


class BrokerConnection(Base):
    """
    Broker connection configuration per tenant.
    Credentials stored encrypted in config_enc.
    """
    __tablename__ = "broker_connections"
    __table_args__ = (
        UniqueConstraint("tenant_id", "broker_type", name="uq_tenant_broker"),
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    broker_type = Column(String(20), nullable=False)  # alpaca, ibkr_tws, ibkr_portal, paper
    config_enc = Column(LargeBinary, nullable=False)  # Encrypted JSON (API keys, host, port, etc.)
    is_active = Column(Boolean, default=True, nullable=False)
    last_connected = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="broker_connections")
    strategies = relationship("Strategy", back_populates="broker_connection")
    
    def __repr__(self):
        return f"<BrokerConnection {self.broker_type} for tenant {self.tenant_id}>"


class Strategy(Base):
    """
    Trading strategy instance (one symbol, one config, one tenant).
    """
    __tablename__ = "strategies"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    broker_conn_id = Column(UUID(as_uuid=True), ForeignKey("broker_connections.id"), nullable=True)
    symbol = Column(String(20), nullable=False, index=True)
    status = Column(String(20), default="stopped", nullable=False)  # stopped, running, paused, error
    config = Column(JSONType, nullable=False)  # All strategy params (check_interval, ladder config, etc.)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="strategies")
    broker_connection = relationship("BrokerConnection", back_populates="strategies")
    positions = relationship("Position", back_populates="strategy", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="strategy", cascade="all, delete-orphan")
    snapshots = relationship("StrategySnapshot", back_populates="strategy", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Strategy {self.symbol} ({self.status}) for tenant {self.tenant_id}>"


class Position(Base):
    """
    Trading positions (open and closed).
    """
    __tablename__ = "positions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    strategy_id = Column(UUID(as_uuid=True), ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    symbol = Column(String(20), nullable=False)
    entry_price = Column(Numeric(18, 8), nullable=False)
    quantity = Column(Numeric(18, 8), nullable=False)
    side = Column(String(4), nullable=False)  # LONG, SHORT
    status = Column(String(10), default="open", nullable=False, index=True)  # open, closed, partial
    rung_index = Column(Integer, nullable=True)  # Ladder rung that triggered this position
    pnl_realized = Column(Numeric(18, 8), default=0, nullable=False)
    opened_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    strategy = relationship("Strategy", back_populates="positions")
    
    def __repr__(self):
        return f"<Position {self.symbol} {self.side} {self.quantity}@{self.entry_price} ({self.status})>"


class Order(Base):
    """
    Order lifecycle tracking (pending, filled, cancelled).
    """
    __tablename__ = "orders"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    strategy_id = Column(UUID(as_uuid=True), ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    broker_order_id = Column(String(100), nullable=True, index=True)
    symbol = Column(String(20), nullable=False)
    side = Column(String(4), nullable=False)  # BUY, SELL
    order_type = Column(String(10), nullable=False)  # LMT, MKT, STP
    quantity = Column(Numeric(18, 8), nullable=False)
    limit_price = Column(Numeric(18, 8), nullable=True)
    status = Column(String(20), nullable=False, index=True)  # pending, filled, partial, cancelled, error
    fill_price = Column(Numeric(18, 8), nullable=True)
    fill_quantity = Column(Numeric(18, 8), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    strategy = relationship("Strategy", back_populates="orders")
    executions = relationship("Execution", back_populates="order", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Order {self.side} {self.quantity} {self.symbol} @ {self.limit_price} ({self.status})>"


class Execution(Base):
    """
    Individual order fills (one order can have multiple partial fills).
    """
    __tablename__ = "executions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    broker_exec_id = Column(String(100), unique=True, nullable=False)
    price = Column(Numeric(18, 8), nullable=False)
    quantity = Column(Numeric(18, 8), nullable=False)
    commission = Column(Numeric(18, 8), default=0, nullable=False)
    executed_at = Column(DateTime(timezone=True), nullable=False)
    
    # Relationships
    order = relationship("Order", back_populates="executions")
    
    def __repr__(self):
        return f"<Execution {self.quantity}@{self.price} (order {self.order_id})>"


class NotificationChannel(Base):
    """
    Notification channels per tenant (Telegram, webhook, email).
    """
    __tablename__ = "notification_channels"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    channel_type = Column(String(20), nullable=False)  # telegram, webhook, email
    config_enc = Column(LargeBinary, nullable=False)  # Encrypted (bot_token, chat_id, url, etc.)
    events = Column(JSONType, default=["fill", "error", "status"], nullable=False)  # Event types to send
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="notification_channels")
    
    def __repr__(self):
        return f"<NotificationChannel {self.channel_type} for tenant {self.tenant_id}>"


class StrategySnapshot(Base):
    """
    Periodic strategy state snapshots for dashboard and analysis.
    """
    __tablename__ = "strategy_snapshots"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    strategy_id = Column(UUID(as_uuid=True), ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    snapshot = Column(JSONType, nullable=False)  # Full dashboard state (positions, ladder, indicators, etc.)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    strategy = relationship("Strategy", back_populates="snapshots")
    
    def __repr__(self):
        return f"<StrategySnapshot for strategy {self.strategy_id} at {self.created_at}>"
