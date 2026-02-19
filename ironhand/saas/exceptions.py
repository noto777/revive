"""
IronHand SaaS Exception Hierarchy

Clean, typed exceptions for all error cases.
Extends the solid foundation from the live bot.
"""


class IronHandException(Exception):
    """Base exception for all IronHand errors."""
    pass


# ============================================================================
# Configuration Errors
# ============================================================================

class ConfigurationError(IronHandException):
    """Base for all configuration-related errors."""
    pass


class InvalidStrategyConfig(ConfigurationError):
    """Strategy configuration is invalid or missing required fields."""
    pass


class InvalidBrokerConfig(ConfigurationError):
    """Broker connection configuration is invalid."""
    pass


class TenantNotFound(ConfigurationError):
    """Requested tenant does not exist."""
    pass


# ============================================================================
# Broker Errors
# ============================================================================

class BrokerError(IronHandException):
    """Base for all broker-related errors."""
    pass


class BrokerConnectionError(BrokerError):
    """Failed to connect to broker."""
    pass


class BrokerAuthenticationError(BrokerError):
    """Broker authentication failed."""
    pass


class OrderRejected(BrokerError):
    """Broker rejected the order."""
    pass


class InsufficientFunds(BrokerError):
    """Account does not have sufficient funds for the operation."""
    pass


class MarketDataError(BrokerError):
    """Failed to retrieve market data."""
    pass


class PositionNotFound(BrokerError):
    """Requested position does not exist."""
    pass


# ============================================================================
# Database Errors
# ============================================================================

class DatabaseError(IronHandException):
    """Base for all database-related errors."""
    pass


class RecordNotFound(DatabaseError):
    """Requested database record does not exist."""
    pass


class DuplicateRecord(DatabaseError):
    """Attempted to create a duplicate record."""
    pass


class TransactionError(DatabaseError):
    """Database transaction failed."""
    pass


# ============================================================================
# Strategy Execution Errors
# ============================================================================

class StrategyError(IronHandException):
    """Base for all strategy execution errors."""
    pass


class StrategyNotRunning(StrategyError):
    """Attempted operation requires strategy to be running."""
    pass


class StrategyAlreadyRunning(StrategyError):
    """Strategy is already running, cannot start again."""
    pass


class InvalidIndicatorData(StrategyError):
    """Indicator calculation failed due to invalid data."""
    pass


class LadderGenerationError(StrategyError):
    """Failed to generate valid ladder rungs."""
    pass


# ============================================================================
# Notification Errors
# ============================================================================

class NotificationError(IronHandException):
    """Base for all notification-related errors."""
    pass


class NotificationChannelError(NotificationError):
    """Failed to send notification through configured channel."""
    pass


class InvalidNotificationConfig(NotificationError):
    """Notification channel configuration is invalid."""
    pass


# ============================================================================
# API Errors
# ============================================================================

class APIError(IronHandException):
    """Base for all API-related errors."""
    pass


class AuthenticationError(APIError):
    """API authentication failed."""
    pass


class AuthorizationError(APIError):
    """User is not authorized for this operation."""
    pass


class RateLimitExceeded(APIError):
    """API rate limit exceeded."""
    pass


class ValidationError(APIError):
    """Request validation failed."""
    pass
