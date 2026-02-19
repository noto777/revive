"""Initial schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-02-14 12:30:00.000000

Creates all tables from SQLAlchemy models:
- tenants
- broker_connections
- strategies
- positions
- orders
- executions
- notification_channels
- strategy_snapshots
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all initial tables."""
    
    # Tenants table
    op.create_table(
        'tenants',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('api_key_hash', sa.String(255), nullable=True),
        sa.Column('plan', sa.String(20), nullable=False, server_default='free'),
        sa.Column('max_strategies', sa.Integer, nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true')
    )
    op.create_index('ix_tenants_email', 'tenants', ['email'])
    
    # Broker connections table
    op.create_table(
        'broker_connections',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('broker_type', sa.String(20), nullable=False),
        sa.Column('config_enc', sa.LargeBinary, nullable=False),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('last_connected', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('tenant_id', 'broker_type', name='uq_tenant_broker')
    )
    op.create_index('ix_broker_connections_tenant', 'broker_connections', ['tenant_id'])
    
    # Strategies table
    op.create_table(
        'strategies',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('broker_conn_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('broker_connections.id'), nullable=True),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='stopped'),
        sa.Column('config', postgresql.JSONB, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
    )
    op.create_index('ix_strategies_tenant', 'strategies', ['tenant_id'])
    op.create_index('ix_strategies_symbol', 'strategies', ['symbol'])
    
    # Positions table
    op.create_table(
        'positions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('strategy_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('strategies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('entry_price', sa.Numeric(18, 8), nullable=False),
        sa.Column('quantity', sa.Numeric(18, 8), nullable=False),
        sa.Column('side', sa.String(4), nullable=False),
        sa.Column('status', sa.String(10), nullable=False, server_default='open'),
        sa.Column('rung_index', sa.Integer, nullable=True),
        sa.Column('pnl_realized', sa.Numeric(18, 8), nullable=False, server_default='0'),
        sa.Column('opened_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index('ix_positions_strategy', 'positions', ['strategy_id', 'status'])
    op.create_index('ix_positions_tenant', 'positions', ['tenant_id'])
    
    # Orders table
    op.create_table(
        'orders',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('strategy_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('strategies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('broker_order_id', sa.String(100), nullable=True),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('side', sa.String(4), nullable=False),
        sa.Column('order_type', sa.String(10), nullable=False),
        sa.Column('quantity', sa.Numeric(18, 8), nullable=False),
        sa.Column('limit_price', sa.Numeric(18, 8), nullable=True),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('fill_price', sa.Numeric(18, 8), nullable=True),
        sa.Column('fill_quantity', sa.Numeric(18, 8), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
    )
    op.create_index('ix_orders_strategy', 'orders', ['strategy_id', 'status'])
    op.create_index('ix_orders_tenant', 'orders', ['tenant_id'])
    op.create_index('ix_orders_broker_id', 'orders', ['broker_order_id'])
    
    # Executions table
    op.create_table(
        'executions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('order_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('orders.id'), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('broker_exec_id', sa.String(100), nullable=False, unique=True),
        sa.Column('price', sa.Numeric(18, 8), nullable=False),
        sa.Column('quantity', sa.Numeric(18, 8), nullable=False),
        sa.Column('commission', sa.Numeric(18, 8), nullable=False, server_default='0'),
        sa.Column('executed_at', sa.DateTime(timezone=True), nullable=False)
    )
    op.create_index('ix_executions_order', 'executions', ['order_id'])
    op.create_index('ix_executions_tenant', 'executions', ['tenant_id'])
    
    # Notification channels table
    op.create_table(
        'notification_channels',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('channel_type', sa.String(20), nullable=False),
        sa.Column('config_enc', sa.LargeBinary, nullable=False),
        sa.Column('events', postgresql.JSONB, nullable=False, server_default='["fill", "error", "status"]'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true')
    )
    op.create_index('ix_notification_channels_tenant', 'notification_channels', ['tenant_id'])
    
    # Strategy snapshots table
    op.create_table(
        'strategy_snapshots',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('strategy_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('strategies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('snapshot', postgresql.JSONB, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
    )
    op.create_index('ix_strategy_snapshots_strategy', 'strategy_snapshots', ['strategy_id'])
    op.create_index('ix_strategy_snapshots_tenant', 'strategy_snapshots', ['tenant_id'])


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table('strategy_snapshots')
    op.drop_table('notification_channels')
    op.drop_table('executions')
    op.drop_table('orders')
    op.drop_table('positions')
    op.drop_table('strategies')
    op.drop_table('broker_connections')
    op.drop_table('tenants')
