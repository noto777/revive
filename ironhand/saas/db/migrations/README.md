# Database Migrations

This directory contains Alembic database migrations for the IronHand SaaS application.

## Setup

Alembic is already configured. The migration system supports both PostgreSQL (production) and SQLite (development).

## Commands

### Initialize database (run all migrations)
```bash
alembic upgrade head
```

### Create a new migration
```bash
# Auto-generate from model changes
alembic revision --autogenerate -m "description of changes"

# Create empty migration template
alembic revision -m "description of changes"
```

### Upgrade/Downgrade
```bash
# Upgrade to latest
alembic upgrade head

# Upgrade one version
alembic upgrade +1

# Downgrade one version
alembic downgrade -1

# Downgrade to specific revision
alembic downgrade <revision_id>

# Downgrade all (back to empty database)
alembic downgrade base
```

### View migration history
```bash
# Show current revision
alembic current

# Show migration history
alembic history

# Show pending migrations
alembic heads
```

## Migration Files

Migrations are stored in `versions/` directory with the naming format:
```
YYYYMMDD_HHMM_<revision_id>_<description>.py
```

### Initial Migration
- **001_initial_schema.py** - Creates all base tables from SQLAlchemy models

## Database Configuration

The database URL is loaded from `config.py` which reads from environment variables:

**SQLite (default for development):**
```bash
export DB_URL="sqlite:///ironhand.db"
```

**PostgreSQL (production):**
```bash
export DB_URL="postgresql+asyncpg://user:pass@localhost/ironhand"
export DB_POOL_SIZE=10
export DB_MAX_OVERFLOW=20
```

## Async Support

The migration environment supports both sync (SQLite) and async (PostgreSQL with asyncpg) database connections. It automatically detects the driver from the connection URL.

## Best Practices

1. **Always review auto-generated migrations** - Alembic's autogenerate is good but not perfect
2. **Test migrations on a copy** - Run upgrade/downgrade on dev before production
3. **Never edit applied migrations** - Create a new migration to fix issues
4. **Use meaningful descriptions** - Future-you will thank you
5. **Keep migrations small** - One logical change per migration when possible

## Tenant Isolation

All tables include `tenant_id` for multi-tenant isolation. Queries should always filter by tenant ID to prevent data leakage.

## Schema Changes Workflow

1. Update models in `db/models.py`
2. Generate migration: `alembic revision --autogenerate -m "add new field"`
3. Review and edit generated migration file
4. Test upgrade: `alembic upgrade head`
5. Test downgrade: `alembic downgrade -1` then `alembic upgrade head`
6. Commit migration file to version control
