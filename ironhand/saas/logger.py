"""
Structured Logging for IronHand SaaS

Replaces all print() statements with proper structured logging.
Every log includes tenant_id for filtering in multi-tenant environment.

Note: Named logger.py (not logging.py) to avoid shadowing Python's logging module.
"""

import logging
import sys
from typing import Any, Optional

import structlog


def setup_logging(
    level: str = "INFO",
    json_logs: bool = True,
    tenant_id: Optional[str] = None
) -> structlog.BoundLogger:
    """
    Configure structured logging for the application.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_logs: If True, output JSON; if False, use human-readable format
        tenant_id: Default tenant_id to bind to all logs from this logger
        
    Returns:
        Configured structlog logger instance
    """
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
    )
    
    # Define processors
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    
    if json_logs:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Get logger and optionally bind tenant_id
    logger = structlog.get_logger()
    if tenant_id:
        logger = logger.bind(tenant_id=tenant_id)
    
    return logger


def get_logger(
    tenant_id: Optional[str] = None,
    **extra_context: Any
) -> structlog.BoundLogger:
    """
    Get a logger instance with optional context binding.
    
    Args:
        tenant_id: Tenant identifier to include in all logs
        **extra_context: Additional key-value pairs to bind to logger
        
    Returns:
        Logger instance with bound context
        
    Example:
        >>> log = get_logger(tenant_id="abc-123", strategy_id="xyz-789")
        >>> log.info("order_placed", symbol="ETHU", qty=10, price=125.50)
    """
    logger = structlog.get_logger()
    
    if tenant_id:
        logger = logger.bind(tenant_id=tenant_id)
    
    if extra_context:
        logger = logger.bind(**extra_context)
    
    return logger
