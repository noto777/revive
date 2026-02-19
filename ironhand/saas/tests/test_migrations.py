"""
Test Database Migrations

Tests for Phase 2 Alembic migration setup. Validates that:
- Alembic config is valid
- Migration scripts run cleanly (up and down)
- Generated schema matches SQLAlchemy models
- No data loss during migrations
"""

import pytest
import os
import tempfile
from pathlib import Path
from sqlalchemy import create_engine, inspect, MetaData, text
from sqlalchemy.orm import sessionmaker
from alembic.config import Config
from alembic import command
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext

# Will be uncommented as implementation lands:
# from ironhand.db.models import Base, Tenant, Strategy, Position, Order, Execution
# from ironhand.db.models import BrokerConnection, NotificationChannel, StrategySnapshot


# ============================================================================
# Alembic Config Tests
# ============================================================================


class TestAlembicConfig:
    """
    Test that Alembic is properly configured.
    """
    
    @pytest.fixture
    def alembic_config_path(self):
        """Path to alembic.ini."""
        # TODO: Update with actual path when created
        project_root = Path(__file__).parent.parent
        config_path = project_root / "alembic.ini"
        return config_path
    
    @pytest.fixture
    def alembic_config(self, alembic_config_path):
        """Alembic Config object."""
        if not alembic_config_path.exists():
            pytest.skip("alembic.ini not created yet")
        return Config(str(alembic_config_path))
    
    @pytest.mark.skip("Waiting for alembic setup")
    def test_alembic_ini_exists(self, alembic_config_path):
        """alembic.ini should exist in project root."""
        assert alembic_config_path.exists(), "alembic.ini not found"
    
    @pytest.mark.skip("Waiting for alembic setup")
    def test_alembic_config_valid(self, alembic_config):
        """Alembic config should be loadable and valid."""
        # Should not raise
        assert alembic_config is not None
        
        # Should have script_location configured
        script_location = alembic_config.get_main_option("script_location")
        assert script_location is not None
        assert "migrations" in script_location or "alembic" in script_location
    
    @pytest.mark.skip("Waiting for alembic setup")
    def test_migrations_directory_exists(self, alembic_config):
        """Migrations directory should exist."""
        script_location = alembic_config.get_main_option("script_location")
        migrations_dir = Path(script_location)
        
        assert migrations_dir.exists(), f"Migrations directory not found: {migrations_dir}"
        assert (migrations_dir / "versions").exists(), "versions/ directory missing"
        assert (migrations_dir / "env.py").exists(), "env.py missing"
    
    @pytest.mark.skip("Waiting for alembic setup")
    def test_env_py_imports_models(self, alembic_config):
        """env.py should import Base for autogenerate."""
        script_location = alembic_config.get_main_option("script_location")
        env_py = Path(script_location) / "env.py"
        
        content = env_py.read_text()
        
        # Should import Base for metadata
        assert "from ironhand.db.models import Base" in content or \
               "import ironhand.db.models" in content, \
               "env.py must import models for autogenerate"


# ============================================================================
# Migration Script Tests
# ============================================================================


class TestMigrationScripts:
    """
    Test individual migration scripts.
    """
    
    @pytest.fixture
    def temp_db_engine(self):
        """Temporary SQLite database for testing migrations."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        
        engine = create_engine(f"sqlite:///{db_path}")
        yield engine
        
        engine.dispose()
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    @pytest.fixture
    def alembic_config_for_testing(self, temp_db_engine, alembic_config_path):
        """Alembic config pointing to temp database."""
        if not alembic_config_path.exists():
            pytest.skip("alembic.ini not created yet")
        
        config = Config(str(alembic_config_path))
        config.set_main_option(
            "sqlalchemy.url",
            str(temp_db_engine.url)
        )
        return config
    
    @pytest.mark.skip("Waiting for alembic setup")
    def test_initial_migration_exists(self, alembic_config):
        """Should have at least one migration (initial schema)."""
        script_dir = ScriptDirectory.from_config(alembic_config)
        revisions = list(script_dir.walk_revisions())
        
        assert len(revisions) > 0, "No migration scripts found"
    
    @pytest.mark.skip("Waiting for alembic setup")
    def test_migration_upgrade_head(self, alembic_config_for_testing, temp_db_engine):
        """Should be able to upgrade to head without errors."""
        # Run migration
        command.upgrade(alembic_config_for_testing, "head")
        
        # Check tables were created
        inspector = inspect(temp_db_engine)
        tables = inspector.get_table_names()
        
        expected_tables = [
            "tenants",
            "broker_connections",
            "strategies",
            "positions",
            "orders",
            "executions",
            "notification_channels",
            "strategy_snapshots",
            "alembic_version"  # Alembic's tracking table
        ]
        
        for table in expected_tables:
            assert table in tables, f"Table '{table}' not created by migration"
    
    @pytest.mark.skip("Waiting for alembic setup")
    def test_migration_downgrade_base(self, alembic_config_for_testing, temp_db_engine):
        """Should be able to downgrade to base (clean rollback)."""
        # Upgrade first
        command.upgrade(alembic_config_for_testing, "head")
        
        # Then downgrade
        command.downgrade(alembic_config_for_testing, "base")
        
        # All tables should be gone (except alembic_version)
        inspector = inspect(temp_db_engine)
        tables = inspector.get_table_names()
        
        # Only alembic_version should remain
        assert "tenants" not in tables
        assert "strategies" not in tables
    
    @pytest.mark.skip("Waiting for alembic setup")
    def test_migration_idempotent(self, alembic_config_for_testing, temp_db_engine):
        """Running upgrade twice should be safe (idempotent)."""
        # First upgrade
        command.upgrade(alembic_config_for_testing, "head")
        
        # Second upgrade (should be no-op)
        command.upgrade(alembic_config_for_testing, "head")
        
        # Should still have tables
        inspector = inspect(temp_db_engine)
        tables = inspector.get_table_names()
        assert "tenants" in tables
    
    @pytest.mark.skip("Waiting for alembic setup")
    def test_no_pending_migrations(self, alembic_config_for_testing, temp_db_engine):
        """After upgrade, autogenerate should detect no changes."""
        # Upgrade to head
        command.upgrade(alembic_config_for_testing, "head")
        
        # Run autogenerate to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            temp_revision_path = f.name
        
        try:
            # This would generate a new migration if schema differs from models
            command.revision(
                alembic_config_for_testing,
                autogenerate=True,
                message="test_pending",
                rev_id="test_pending"
            )
            
            # Check if the generated migration is empty (no changes)
            script_dir = ScriptDirectory.from_config(alembic_config_for_testing)
            latest = script_dir.get_current_head()
            
            # Read the migration file
            revision = script_dir.get_revision(latest)
            revision_file = Path(revision.path)
            content = revision_file.read_text()
            
            # An empty migration will have pass statements in upgrade/downgrade
            # or no operations
            assert "pass" in content or "op.create_table" not in content, \
                "Autogenerate detected schema drift - models don't match migrations"
        
        finally:
            # Cleanup test revision
            if os.path.exists(temp_revision_path):
                os.unlink(temp_revision_path)


# ============================================================================
# Schema Validation Tests
# ============================================================================


class TestSchemaMatchesModels:
    """
    Verify that the migrated schema matches SQLAlchemy models exactly.
    """
    
    @pytest.fixture
    def migrated_engine(self, alembic_config_for_testing):
        """Database with migrations applied."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        
        engine = create_engine(f"sqlite:///{db_path}")
        
        # Apply migrations
        config = alembic_config_for_testing
        config.set_main_option("sqlalchemy.url", str(engine.url))
        command.upgrade(config, "head")
        
        yield engine
        
        engine.dispose()
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    @pytest.fixture
    def model_engine(self):
        """Fresh database with models created directly."""
        # TODO: Uncomment when models are ready
        # from ironhand.db.models import Base
        # 
        # with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        #     db_path = f.name
        # 
        # engine = create_engine(f"sqlite:///{db_path}")
        # Base.metadata.create_all(engine)
        # 
        # yield engine
        # 
        # engine.dispose()
        # if os.path.exists(db_path):
        #     os.unlink(db_path)
        pytest.skip("Waiting for db.models implementation")
    
    @pytest.mark.skip("Waiting for full implementation")
    def test_table_names_match(self, migrated_engine, model_engine):
        """Migrated schema should have same tables as models."""
        migrated_inspector = inspect(migrated_engine)
        model_inspector = inspect(model_engine)
        
        migrated_tables = set(migrated_inspector.get_table_names())
        model_tables = set(model_inspector.get_table_names())
        
        # Remove alembic_version from comparison
        migrated_tables.discard("alembic_version")
        
        assert migrated_tables == model_tables, \
            f"Table mismatch. Migrated: {migrated_tables}, Models: {model_tables}"
    
    @pytest.mark.skip("Waiting for full implementation")
    def test_tenant_table_columns_match(self, migrated_engine, model_engine):
        """Tenants table schema should match model."""
        migrated_inspector = inspect(migrated_engine)
        model_inspector = inspect(model_engine)
        
        migrated_cols = {c['name']: c for c in migrated_inspector.get_columns('tenants')}
        model_cols = {c['name']: c for c in model_inspector.get_columns('tenants')}
        
        assert set(migrated_cols.keys()) == set(model_cols.keys()), \
            f"Column mismatch in tenants table"
        
        # Check specific important columns
        assert migrated_cols['id']['type'] is not None
        assert migrated_cols['email']['nullable'] == False
        assert migrated_cols['is_active']['default'] is not None
    
    @pytest.mark.skip("Waiting for full implementation")
    def test_all_indexes_created(self, migrated_engine):
        """All indexes from ARCHITECTURE.md should be created."""
        inspector = inspect(migrated_engine)
        
        # Check positions indexes
        positions_indexes = inspector.get_indexes('positions')
        position_index_cols = [idx['column_names'] for idx in positions_indexes]
        
        # Should have index on (strategy_id, status)
        assert any('strategy_id' in cols for cols in position_index_cols), \
            "Missing index on positions.strategy_id"
        
        # Check orders indexes
        orders_indexes = inspector.get_indexes('orders')
        order_index_cols = [idx['column_names'] for idx in orders_indexes]
        
        assert any('strategy_id' in cols for cols in order_index_cols), \
            "Missing index on orders.strategy_id"
    
    @pytest.mark.skip("Waiting for full implementation")
    def test_foreign_keys_created(self, migrated_engine):
        """All foreign key relationships should be in place."""
        inspector = inspect(migrated_engine)
        
        # Strategies should have FK to tenants
        strategy_fks = inspector.get_foreign_keys('strategies')
        fk_tables = [fk['referred_table'] for fk in strategy_fks]
        
        assert 'tenants' in fk_tables, "Missing FK from strategies to tenants"
        assert 'broker_connections' in fk_tables, "Missing FK from strategies to broker_connections"
        
        # Positions should have FK to strategies
        position_fks = inspector.get_foreign_keys('positions')
        fk_tables = [fk['referred_table'] for fk in position_fks]
        
        assert 'strategies' in fk_tables, "Missing FK from positions to strategies"
    
    @pytest.mark.skip("Waiting for full implementation")
    def test_unique_constraints(self, migrated_engine):
        """Unique constraints should be enforced."""
        inspector = inspect(migrated_engine)
        
        # Tenant email should be unique
        tenant_indexes = inspector.get_indexes('tenants')
        tenant_unique = [idx for idx in tenant_indexes if idx.get('unique')]
        tenant_unique_cols = [idx['column_names'] for idx in tenant_unique]
        
        assert any('email' in cols for cols in tenant_unique_cols), \
            "Tenant email should have unique constraint"
        
        # Broker connection (tenant_id, broker_type) should be unique
        broker_indexes = inspector.get_indexes('broker_connections')
        broker_unique = [idx for idx in broker_indexes if idx.get('unique')]
        
        # Check if composite unique constraint exists
        # (This may be implemented as constraint rather than index)


# ============================================================================
# Data Migration Tests
# ============================================================================


class TestDataPreservation:
    """
    Test that data survives migration upgrades/downgrades.
    """
    
    @pytest.mark.skip("Waiting for full implementation")
    async def test_data_preserved_after_upgrade(self, alembic_config_for_testing):
        """Upgrading should not lose existing data."""
        from ironhand.db.models import Tenant, Base
        
        # Create temp db
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        
        try:
            engine = create_engine(f"sqlite:///{db_path}")
            
            # Create schema (initial migration)
            config = alembic_config_for_testing
            config.set_main_option("sqlalchemy.url", str(engine.url))
            command.upgrade(config, "head")
            
            # Insert test data
            Session = sessionmaker(bind=engine)
            session = Session()
            
            tenant = Tenant(
                name="Test User",
                email="test@example.com",
                plan="free"
            )
            session.add(tenant)
            session.commit()
            tenant_id = tenant.id
            session.close()
            
            # If there's a second migration, apply it
            # (This test becomes more relevant with multiple migrations)
            # command.upgrade(config, "+1")
            
            # Verify data still exists
            session = Session()
            loaded_tenant = session.query(Tenant).filter_by(id=tenant_id).first()
            
            assert loaded_tenant is not None
            assert loaded_tenant.email == "test@example.com"
            assert loaded_tenant.plan == "free"
            
            session.close()
            engine.dispose()
        
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)


# ============================================================================
# Migration Dependency Tests
# ============================================================================


class TestMigrationDependencies:
    """
    Test migration revision chain integrity.
    """
    
    @pytest.mark.skip("Waiting for alembic setup")
    def test_no_duplicate_revisions(self, alembic_config):
        """Should not have duplicate revision IDs."""
        script_dir = ScriptDirectory.from_config(alembic_config)
        revisions = list(script_dir.walk_revisions())
        
        revision_ids = [rev.revision for rev in revisions]
        
        assert len(revision_ids) == len(set(revision_ids)), \
            "Duplicate revision IDs found"
    
    @pytest.mark.skip("Waiting for alembic setup")
    def test_linear_revision_chain(self, alembic_config):
        """For Phase 2, should have simple linear chain (no branches)."""
        script_dir = ScriptDirectory.from_config(alembic_config)
        
        # Get head(s)
        heads = script_dir.get_heads()
        
        # Should only have one head (linear chain)
        assert len(heads) == 1, \
            f"Found {len(heads)} heads - expected 1 (linear chain)"
    
    @pytest.mark.skip("Waiting for alembic setup")
    def test_all_revisions_reachable(self, alembic_config):
        """All revisions should be in dependency chain from head."""
        script_dir = ScriptDirectory.from_config(alembic_config)
        
        head = script_dir.get_current_head()
        all_revisions = list(script_dir.walk_revisions())
        reachable_from_head = list(script_dir.walk_revisions(head, "base"))
        
        assert len(all_revisions) == len(reachable_from_head), \
            "Found orphaned migration revisions not in main chain"


# ============================================================================
# PostgreSQL vs SQLite Compatibility Tests
# ============================================================================


class TestDatabaseCompatibility:
    """
    Test that migrations work for both PostgreSQL (prod) and SQLite (dev/test).
    """
    
    @pytest.mark.skip("Waiting for full implementation")
    def test_jsonb_vs_json_compatibility(self):
        """JSONB (Postgres) should fall back to JSON (SQLite) cleanly."""
        from ironhand.db.models import Strategy
        
        # SQLite engine
        sqlite_engine = create_engine("sqlite:///:memory:")
        
        # This should not raise even though model uses JSONB
        Strategy.__table__.create(sqlite_engine)
        
        inspector = inspect(sqlite_engine)
        columns = {c['name']: c for c in inspector.get_columns('strategies')}
        
        # Config column should exist
        assert 'config' in columns
    
    @pytest.mark.skip("Waiting for full implementation")
    def test_uuid_compatibility(self):
        """UUID type should work in both Postgres and SQLite."""
        from ironhand.db.models import Tenant
        
        # SQLite engine
        sqlite_engine = create_engine("sqlite:///:memory:")
        Tenant.__table__.create(sqlite_engine)
        
        Session = sessionmaker(bind=sqlite_engine)
        session = Session()
        
        # Should be able to create tenant with UUID
        tenant = Tenant(
            name="Test",
            email="test@example.com"
        )
        session.add(tenant)
        session.commit()
        
        # ID should be UUID
        assert tenant.id is not None
        assert isinstance(str(tenant.id), str)  # UUID string representation
        
        session.close()


# ============================================================================
# Performance Tests
# ============================================================================


class TestMigrationPerformance:
    """
    Sanity check that migrations complete in reasonable time.
    """
    
    @pytest.mark.skip("Waiting for full implementation")
    def test_migration_completes_quickly(self, alembic_config_for_testing):
        """Migration should complete in under 10 seconds."""
        import time
        
        start = time.time()
        command.upgrade(alembic_config_for_testing, "head")
        elapsed = time.time() - start
        
        assert elapsed < 10, f"Migration took {elapsed}s (expected < 10s)"
    
    @pytest.mark.skip("Waiting for full implementation")
    def test_downgrade_completes_quickly(self, alembic_config_for_testing):
        """Downgrade should also be fast."""
        import time
        
        # Upgrade first
        command.upgrade(alembic_config_for_testing, "head")
        
        start = time.time()
        command.downgrade(alembic_config_for_testing, "base")
        elapsed = time.time() - start
        
        assert elapsed < 10, f"Downgrade took {elapsed}s (expected < 10s)"
