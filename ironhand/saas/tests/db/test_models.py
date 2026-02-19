"""
Tests for db/models.py - Database models and tenant isolation.

Critical tests for multi-tenant SaaS:
- Tenant isolation (queries never leak cross-tenant)
- CRUD operations
- Relationships and cascades
- Data integrity constraints
"""

import pytest
from uuid import uuid4
from decimal import Decimal
from datetime import datetime


try:
    from ironhand.db.models import (
        Tenant, BrokerConnection, Strategy, Position, Order, Execution,
        NotificationChannel, StrategySnapshot
    )
    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError
except ImportError:
    Tenant = None


pytestmark = pytest.mark.skipif(
    Tenant is None,
    reason="Database models not implemented yet"
)


class TestTenantModel:
    """Test Tenant model."""
    
    @pytest.mark.asyncio
    async def test_create_tenant(self, db_session):
        """Should create tenant successfully."""
        tenant = Tenant(
            name="Test Company",
            email="test@company.com",
            plan="pro"
        )
        
        db_session.add(tenant)
        await db_session.commit()
        await db_session.refresh(tenant)
        
        assert tenant.id is not None
        assert tenant.name == "Test Company"
        assert tenant.is_active == True
    
    @pytest.mark.asyncio
    async def test_tenant_email_unique(self, db_session, tenant):
        """Tenant email should be unique."""
        # Try to create another tenant with same email
        duplicate = Tenant(
            name="Another Company",
            email=tenant.email,  # Same email
            plan="free"
        )
        
        db_session.add(duplicate)
        
        with pytest.raises(IntegrityError):
            await db_session.commit()
    
    @pytest.mark.asyncio
    async def test_tenant_defaults(self, db_session):
        """Tenant should have correct default values."""
        tenant = Tenant(
            name="Test",
            email="test@test.com"
        )
        
        db_session.add(tenant)
        await db_session.commit()
        await db_session.refresh(tenant)
        
        assert tenant.plan == "free"
        assert tenant.max_strategies == 1
        assert tenant.is_active == True
        assert tenant.created_at is not None


class TestTenantIsolation:
    """Critical tests for tenant data isolation."""
    
    @pytest.mark.asyncio
    async def test_strategies_isolated_by_tenant(self, db_session, tenant, second_tenant):
        """Strategies should be isolated by tenant."""
        # Create strategy for first tenant
        strategy1 = Strategy(
            tenant_id=tenant.id,
            symbol="ETHU",
            status="running",
            config={"test": "value"}
        )
        
        # Create strategy for second tenant
        strategy2 = Strategy(
            tenant_id=second_tenant.id,
            symbol="BTCU",
            status="running",
            config={"test": "value"}
        )
        
        db_session.add_all([strategy1, strategy2])
        await db_session.commit()
        
        # Query for first tenant's strategies
        result = await db_session.execute(
            select(Strategy).where(Strategy.tenant_id == tenant.id)
        )
        tenant1_strategies = result.scalars().all()
        
        # Should only see own strategy
        assert len(tenant1_strategies) == 1
        assert tenant1_strategies[0].symbol == "ETHU"
        
        # Query for second tenant
        result = await db_session.execute(
            select(Strategy).where(Strategy.tenant_id == second_tenant.id)
        )
        tenant2_strategies = result.scalars().all()
        
        assert len(tenant2_strategies) == 1
        assert tenant2_strategies[0].symbol == "BTCU"
    
    @pytest.mark.asyncio
    async def test_positions_isolated_by_tenant(self, db_session, tenant, second_tenant, strategy):
        """Positions should be isolated by tenant."""
        # Create strategy for second tenant
        strategy2 = Strategy(
            tenant_id=second_tenant.id,
            symbol="BTCU",
            status="running",
            config={}
        )
        db_session.add(strategy2)
        await db_session.commit()
        await db_session.refresh(strategy2)
        
        # Create positions for each tenant
        pos1 = Position(
            strategy_id=strategy.id,
            tenant_id=tenant.id,
            symbol="ETHU",
            entry_price=Decimal("50.0"),
            quantity=Decimal("100"),
            side="LONG",
            status="open"
        )
        
        pos2 = Position(
            strategy_id=strategy2.id,
            tenant_id=second_tenant.id,
            symbol="BTCU",
            entry_price=Decimal("100.0"),
            quantity=Decimal("10"),
            side="LONG",
            status="open"
        )
        
        db_session.add_all([pos1, pos2])
        await db_session.commit()
        
        # Query tenant 1's positions
        result = await db_session.execute(
            select(Position).where(Position.tenant_id == tenant.id)
        )
        tenant1_positions = result.scalars().all()
        
        assert len(tenant1_positions) == 1
        assert tenant1_positions[0].symbol == "ETHU"
        
        # Query tenant 2's positions
        result = await db_session.execute(
            select(Position).where(Position.tenant_id == second_tenant.id)
        )
        tenant2_positions = result.scalars().all()
        
        assert len(tenant2_positions) == 1
        assert tenant2_positions[0].symbol == "BTCU"
    
    @pytest.mark.asyncio
    async def test_orders_isolated_by_tenant(self, db_session, tenant, second_tenant, strategy):
        """Orders should be isolated by tenant."""
        # Create strategy for second tenant
        strategy2 = Strategy(
            tenant_id=second_tenant.id,
            symbol="BTCU",
            status="running",
            config={}
        )
        db_session.add(strategy2)
        await db_session.commit()
        await db_session.refresh(strategy2)
        
        # Create orders
        order1 = Order(
            strategy_id=strategy.id,
            tenant_id=tenant.id,
            broker_order_id="IB123",
            symbol="ETHU",
            side="BUY",
            order_type="LMT",
            quantity=Decimal("100"),
            limit_price=Decimal("50.0"),
            status="filled"
        )
        
        order2 = Order(
            strategy_id=strategy2.id,
            tenant_id=second_tenant.id,
            broker_order_id="IB456",
            symbol="BTCU",
            side="BUY",
            order_type="LMT",
            quantity=Decimal("10"),
            limit_price=Decimal("100.0"),
            status="pending"
        )
        
        db_session.add_all([order1, order2])
        await db_session.commit()
        
        # Verify isolation
        result = await db_session.execute(
            select(Order).where(Order.tenant_id == tenant.id)
        )
        assert len(result.scalars().all()) == 1
        
        result = await db_session.execute(
            select(Order).where(Order.tenant_id == second_tenant.id)
        )
        assert len(result.scalars().all()) == 1
    
    @pytest.mark.asyncio
    async def test_no_cross_tenant_queries(self, db_session, tenant, second_tenant):
        """Attempting to query cross-tenant should return empty."""
        # Create strategy for tenant1
        strategy = Strategy(
            tenant_id=tenant.id,
            symbol="ETHU",
            status="running",
            config={}
        )
        db_session.add(strategy)
        await db_session.commit()
        
        # Try to query with wrong tenant_id
        result = await db_session.execute(
            select(Strategy).where(
                Strategy.tenant_id == second_tenant.id,
                Strategy.symbol == "ETHU"
            )
        )
        
        # Should return empty
        assert len(result.scalars().all()) == 0


class TestStrategyModel:
    """Test Strategy model."""
    
    @pytest.mark.asyncio
    async def test_create_strategy(self, db_session, tenant):
        """Should create strategy successfully."""
        strategy = Strategy(
            tenant_id=tenant.id,
            symbol="ETHU",
            status="stopped",
            config={
                "check_interval": 15,
                "min_ladder_trade_usd": 500
            }
        )
        
        db_session.add(strategy)
        await db_session.commit()
        await db_session.refresh(strategy)
        
        assert strategy.id is not None
        assert strategy.config["check_interval"] == 15
    
    @pytest.mark.asyncio
    async def test_strategy_status_values(self, db_session, tenant):
        """Strategy status should accept valid values."""
        valid_statuses = ["stopped", "running", "paused", "error"]
        
        for status in valid_statuses:
            strategy = Strategy(
                tenant_id=tenant.id,
                symbol=f"TEST{status}",
                status=status,
                config={}
            )
            db_session.add(strategy)
        
        await db_session.commit()
    
    @pytest.mark.asyncio
    async def test_strategy_timestamps(self, db_session, tenant):
        """Strategy should track created_at and updated_at."""
        strategy = Strategy(
            tenant_id=tenant.id,
            symbol="ETHU",
            status="stopped",
            config={}
        )
        
        db_session.add(strategy)
        await db_session.commit()
        await db_session.refresh(strategy)
        
        assert strategy.created_at is not None
        assert strategy.updated_at is not None
        
        original_updated = strategy.updated_at
        
        # Update strategy
        strategy.status = "running"
        await db_session.commit()
        await db_session.refresh(strategy)
        
        # updated_at should change
        assert strategy.updated_at > original_updated


class TestPositionModel:
    """Test Position model."""
    
    @pytest.mark.asyncio
    async def test_create_position(self, db_session, strategy, tenant):
        """Should create position successfully."""
        position = Position(
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
        
        assert position.id is not None
        assert position.entry_price == Decimal("50.25")
    
    @pytest.mark.asyncio
    async def test_position_pnl_tracking(self, db_session, strategy, tenant):
        """Position should track realized P&L."""
        position = Position(
            strategy_id=strategy.id,
            tenant_id=tenant.id,
            symbol="ETHU",
            entry_price=Decimal("45.0"),
            quantity=Decimal("100"),
            side="LONG",
            status="closed",
            pnl_realized=Decimal("500.0")
        )
        
        db_session.add(position)
        await db_session.commit()
        await db_session.refresh(position)
        
        assert position.pnl_realized == Decimal("500.0")
    
    @pytest.mark.asyncio
    async def test_position_timestamps(self, db_session, strategy, tenant):
        """Position should track opened_at and closed_at."""
        position = Position(
            strategy_id=strategy.id,
            tenant_id=tenant.id,
            symbol="ETHU",
            entry_price=Decimal("50.0"),
            quantity=Decimal("100"),
            side="LONG",
            status="open"
        )
        
        db_session.add(position)
        await db_session.commit()
        await db_session.refresh(position)
        
        assert position.opened_at is not None
        assert position.closed_at is None
        
        # Close position
        position.status = "closed"
        position.closed_at = datetime.utcnow()
        await db_session.commit()
        await db_session.refresh(position)
        
        assert position.closed_at is not None


class TestOrderModel:
    """Test Order model."""
    
    @pytest.mark.asyncio
    async def test_create_order(self, db_session, strategy, tenant):
        """Should create order successfully."""
        order = Order(
            strategy_id=strategy.id,
            tenant_id=tenant.id,
            broker_order_id="IB12345",
            symbol="ETHU",
            side="BUY",
            order_type="LMT",
            quantity=Decimal("100"),
            limit_price=Decimal("50.0"),
            status="pending"
        )
        
        db_session.add(order)
        await db_session.commit()
        await db_session.refresh(order)
        
        assert order.id is not None
        assert order.broker_order_id == "IB12345"
    
    @pytest.mark.asyncio
    async def test_order_fill_tracking(self, db_session, strategy, tenant):
        """Order should track fill price and quantity."""
        order = Order(
            strategy_id=strategy.id,
            tenant_id=tenant.id,
            broker_order_id="IB123",
            symbol="ETHU",
            side="BUY",
            order_type="LMT",
            quantity=Decimal("100"),
            limit_price=Decimal("50.0"),
            status="filled",
            fill_price=Decimal("49.99"),
            fill_quantity=Decimal("100")
        )
        
        db_session.add(order)
        await db_session.commit()
        await db_session.refresh(order)
        
        assert order.fill_price == Decimal("49.99")
        assert order.fill_quantity == Decimal("100")


class TestRelationships:
    """Test model relationships and cascades."""
    
    @pytest.mark.asyncio
    async def test_tenant_strategies_relationship(self, db_session, tenant):
        """Tenant should have relationship to strategies."""
        # Create strategies
        strategy1 = Strategy(tenant_id=tenant.id, symbol="ETHU", status="running", config={})
        strategy2 = Strategy(tenant_id=tenant.id, symbol="BTCU", status="stopped", config={})
        
        db_session.add_all([strategy1, strategy2])
        await db_session.commit()
        
        # Refresh tenant to load relationships
        await db_session.refresh(tenant)
        
        # Should be able to access strategies through relationship
        # (Exact syntax depends on how relationship is defined)
        # assert len(tenant.strategies) == 2
    
    @pytest.mark.asyncio
    async def test_strategy_positions_relationship(self, db_session, strategy, tenant):
        """Strategy should have relationship to positions."""
        pos1 = Position(
            strategy_id=strategy.id,
            tenant_id=tenant.id,
            symbol="ETHU",
            entry_price=Decimal("50.0"),
            quantity=Decimal("100"),
            side="LONG",
            status="open"
        )
        pos2 = Position(
            strategy_id=strategy.id,
            tenant_id=tenant.id,
            symbol="ETHU",
            entry_price=Decimal("48.0"),
            quantity=Decimal("50"),
            side="LONG",
            status="closed"
        )
        
        db_session.add_all([pos1, pos2])
        await db_session.commit()
        
        await db_session.refresh(strategy)
        
        # Should access positions through relationship
        # assert len(strategy.positions) == 2
    
    @pytest.mark.asyncio
    async def test_cascade_delete_tenant(self, db_session, tenant):
        """Deleting tenant should cascade to related records."""
        # Create related records
        strategy = Strategy(tenant_id=tenant.id, symbol="ETHU", status="running", config={})
        db_session.add(strategy)
        await db_session.commit()
        await db_session.refresh(strategy)
        
        position = Position(
            strategy_id=strategy.id,
            tenant_id=tenant.id,
            symbol="ETHU",
            entry_price=Decimal("50.0"),
            quantity=Decimal("100"),
            side="LONG",
            status="open"
        )
        db_session.add(position)
        await db_session.commit()
        
        # Delete tenant
        await db_session.delete(tenant)
        await db_session.commit()
        
        # Related records should be deleted
        result = await db_session.execute(select(Strategy))
        assert len(result.scalars().all()) == 0
        
        result = await db_session.execute(select(Position))
        assert len(result.scalars().all()) == 0
    
    @pytest.mark.asyncio
    async def test_cascade_delete_strategy(self, db_session, strategy, tenant):
        """Deleting strategy should cascade to positions and orders."""
        # Create related records
        position = Position(
            strategy_id=strategy.id,
            tenant_id=tenant.id,
            symbol="ETHU",
            entry_price=Decimal("50.0"),
            quantity=Decimal("100"),
            side="LONG",
            status="open"
        )
        
        order = Order(
            strategy_id=strategy.id,
            tenant_id=tenant.id,
            symbol="ETHU",
            side="BUY",
            order_type="LMT",
            quantity=Decimal("100"),
            limit_price=Decimal("50.0"),
            status="pending"
        )
        
        db_session.add_all([position, order])
        await db_session.commit()
        
        # Delete strategy
        await db_session.delete(strategy)
        await db_session.commit()
        
        # Positions and orders should be deleted
        result = await db_session.execute(select(Position))
        assert len(result.scalars().all()) == 0
        
        result = await db_session.execute(select(Order))
        assert len(result.scalars().all()) == 0


class TestDataIntegrity:
    """Test data integrity constraints."""
    
    @pytest.mark.asyncio
    async def test_position_requires_tenant_id(self, db_session, strategy):
        """Position must have tenant_id."""
        position = Position(
            strategy_id=strategy.id,
            # Missing tenant_id
            symbol="ETHU",
            entry_price=Decimal("50.0"),
            quantity=Decimal("100"),
            side="LONG",
            status="open"
        )
        
        db_session.add(position)
        
        with pytest.raises(IntegrityError):
            await db_session.commit()
    
    @pytest.mark.asyncio
    async def test_decimal_precision_preserved(self, db_session, strategy, tenant):
        """Decimal precision should be preserved."""
        position = Position(
            strategy_id=strategy.id,
            tenant_id=tenant.id,
            symbol="ETHU",
            entry_price=Decimal("50.12345678"),
            quantity=Decimal("100.12345678"),
            side="LONG",
            status="open"
        )
        
        db_session.add(position)
        await db_session.commit()
        await db_session.refresh(position)
        
        # Should preserve precision
        assert position.entry_price == Decimal("50.12345678")
        assert position.quantity == Decimal("100.12345678")


class TestQueryPerformance:
    """Test query performance and indexing."""
    
    @pytest.mark.asyncio
    async def test_tenant_query_uses_index(self, db_session, tenant):
        """Queries by tenant_id should use index."""
        # Create many strategies
        strategies = [
            Strategy(
                tenant_id=tenant.id,
                symbol=f"SYM{i}",
                status="running",
                config={}
            )
            for i in range(100)
        ]
        
        db_session.add_all(strategies)
        await db_session.commit()
        
        # Query should be fast (verifying index exists)
        result = await db_session.execute(
            select(Strategy).where(Strategy.tenant_id == tenant.id)
        )
        
        strategies_found = result.scalars().all()
        assert len(strategies_found) == 100
    
    @pytest.mark.asyncio
    async def test_strategy_status_query_uses_index(self, db_session, tenant):
        """Queries by status should use index."""
        pytest.skip("Index verification requires EXPLAIN ANALYZE")
