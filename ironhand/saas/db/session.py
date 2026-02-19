"""
Database session management and connection factory.

Handles both PostgreSQL (production) and SQLite (development).
Thread-safe session management with context managers.
"""

from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from settings import get_settings
from logger import get_logger

logger = get_logger()


# Global engine and session factory
_engine: Optional[Engine] = None
_SessionFactory: Optional[sessionmaker] = None
_async_engine = None
_AsyncSessionFactory = None


def get_async_session_maker():
    global _async_engine, _AsyncSessionFactory
    if _AsyncSessionFactory:
        return _AsyncSessionFactory
    
    settings = get_settings()
    db_url = settings.database.url
    
    # Force async driver
    if db_url.startswith("sqlite"):
        if "aiosqlite" not in db_url:
            db_url = db_url.replace("sqlite://", "sqlite+aiosqlite://")
    elif db_url.startswith("postgresql"):
        if "asyncpg" not in db_url:
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
            
    if _async_engine is None:
        _async_engine = create_async_engine(db_url, echo=settings.database.echo)
        
    _AsyncSessionFactory = async_sessionmaker(bind=_async_engine, expire_on_commit=False)
    return _AsyncSessionFactory


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """
    Enable WAL mode and foreign keys for SQLite connections.
    
    This ensures:
    - WAL mode for better concurrency
    - Foreign key constraints are enforced
    """
    if "sqlite" in str(dbapi_conn):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def init_db() -> Engine:
    """
    Initialize the database engine and session factory.
    
    Returns:
        SQLAlchemy engine
    """
    global _engine, _SessionFactory
    
    if _engine is not None:
        return _engine
    
    settings = get_settings()
    db_url = settings.database.url
    
    logger.info(
        "initializing_database",
        url=db_url.split("@")[-1] if "@" in db_url else db_url,  # Hide credentials
        echo=settings.database.echo
    )
    
    # SQLite-specific config (single-threaded, in-memory support)
    if db_url.startswith("sqlite"):
        _engine = create_engine(
            db_url,
            echo=settings.database.echo,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        # PostgreSQL config
        _engine = create_engine(
            db_url,
            echo=settings.database.echo,
            pool_size=settings.database.pool_size,
            max_overflow=settings.database.max_overflow,
            pool_pre_ping=True,  # Verify connections before using
        )
    
    _SessionFactory = sessionmaker(
        bind=_engine,
        autocommit=False,
        autoflush=False,
    )
    
    logger.info("database_initialized")
    return _engine


def get_session() -> Session:
    """
    Get a new database session.
    
    Caller is responsible for closing the session.
    Prefer using `session_scope()` context manager instead.
    
    Returns:
        New SQLAlchemy session
    """
    if _SessionFactory is None:
        init_db()
    
    return _SessionFactory()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """
    Provide a transactional scope for database operations.
    
    Automatically commits on success, rolls back on exception.
    
    Yields:
        Database session
        
    Example:
        >>> with session_scope() as session:
        ...     tenant = session.query(Tenant).filter_by(email="user@example.com").first()
        ...     tenant.is_active = True
        ...     # Auto-commits here
    """
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error("database_transaction_failed", error=str(e))
        raise
    finally:
        session.close()


def create_tables(engine: Optional[Engine] = None):
    """
    Create all tables defined in models.
    
    Args:
        engine: SQLAlchemy engine (uses global if not provided)
    """
    from .models import Base
    
    if engine is None:
        engine = init_db()
    
    logger.info("creating_database_tables")
    Base.metadata.create_all(bind=engine)
    logger.info("database_tables_created")


def drop_tables(engine: Optional[Engine] = None):
    """
    Drop all tables (USE WITH CAUTION).
    
    Args:
        engine: SQLAlchemy engine (uses global if not provided)
    """
    from .models import Base
    
    if engine is None:
        engine = init_db()
    
    logger.warning("dropping_all_database_tables")
    Base.metadata.drop_all(bind=engine)
    logger.warning("database_tables_dropped")
