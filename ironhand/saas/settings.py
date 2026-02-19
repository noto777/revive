"""
Configuration Management for IronHand SaaS

Replaces module-level globals with Pydantic Settings.
Supports environment variables and per-tenant overrides.
"""

from decimal import Decimal
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database connection configuration."""
    
    model_config = SettingsConfigDict(
        env_prefix="DB_",
        case_sensitive=False,
    )
    
    url: str = Field(
        default="sqlite:///ironhand.db",
        description="Database connection URL (PostgreSQL or SQLite)"
    )
    echo: bool = Field(
        default=False,
        description="Echo SQL queries (debug mode)"
    )
    pool_size: int = Field(
        default=5,
        description="Connection pool size (PostgreSQL only)"
    )
    max_overflow: int = Field(
        default=10,
        description="Max overflow connections (PostgreSQL only)"
    )


class APISettings(BaseSettings):
    """API server configuration."""
    
    model_config = SettingsConfigDict(
        env_prefix="API_",
        case_sensitive=False,
    )
    
    host: str = Field(default="0.0.0.0", description="API server host")
    port: int = Field(default=8000, description="API server port")
    workers: int = Field(default=1, description="Number of worker processes")
    jwt_secret: str = Field(..., description="JWT signing secret")
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_expiry_hours: int = Field(default=24, description="JWT token expiry in hours")


class BrokerSettings(BaseSettings):
    """Default broker configuration (can be overridden per tenant)."""
    
    model_config = SettingsConfigDict(
        env_prefix="BROKER_",
        case_sensitive=False,
    )
    
    default_type: str = Field(
        default="alpaca",
        description="Default broker type (alpaca, ibkr_tws, paper)"
    )
    alpaca_api_key: Optional[str] = Field(
        default=None,
        description="Alpaca API key"
    )
    alpaca_secret_key: Optional[str] = Field(
        default=None,
        description="Alpaca secret key"
    )
    alpaca_base_url: str = Field(
        default="https://paper-api.alpaca.markets",
        description="Alpaca API base URL"
    )


class StrategySettings(BaseSettings):
    """
    Default strategy parameters.
    
    These replace the old regime-based system (all three regimes
    had identical params). Per-tenant overrides stored in DB.
    """
    
    model_config = SettingsConfigDict(
        env_prefix="STRATEGY_",
        case_sensitive=False,
    )
    
    # Execution timing
    check_interval: int = Field(
        default=15,
        description="Strategy check interval in seconds",
        ge=1,
        le=300
    )
    
    # Ladder configuration
    min_ladder_trade_usd: Decimal = Field(
        default=Decimal("500.00"),
        description="Minimum trade size in USD per ladder rung"
    )
    start_atr: Decimal = Field(
        default=Decimal("0.2"),
        description="Starting ATR multiplier for first ladder rung"
    )
    end_atr: Decimal = Field(
        default=Decimal("0.6"),
        description="Ending ATR multiplier for last ladder rung"
    )
    distribution_curve: Decimal = Field(
        default=Decimal("1.0"),
        description="Ladder distribution curve exponent (1.0 = linear)"
    )
    size_increase_factor: Decimal = Field(
        default=Decimal("1.25"),
        description="Size multiplier per rung (e.g., 1.25 = 25% larger)"
    )
    
    # Core position management
    max_core_pct: Decimal = Field(
        default=Decimal("15.0"),
        description="Maximum core position as % of account value"
    )
    core_hysteresis_gap: Decimal = Field(
        default=Decimal("2.0"),
        description="Hysteresis gap above max_core_pct to trigger rebalancing"
    )
    
    # Scale-out configuration
    scale_out_pct: Decimal = Field(
        default=Decimal("15.0"),
        description="Percentage to sell at each profit step"
    )
    scale_out_step: Decimal = Field(
        default=Decimal("4.0"),
        description="Profit step size in % for scale-out (e.g., 4% = sell at 4%, 8%, 12%...)"
    )
    
    # Profit lock (trailing stop)
    profit_lock_arm: Decimal = Field(
        default=Decimal("12.0"),
        description="Profit % to arm the trailing stop"
    )
    profit_lock_trail: Decimal = Field(
        default=Decimal("4.0"),
        description="Trail distance in % below high water mark"
    )
    
    @field_validator("start_atr", "end_atr", mode="before")
    @classmethod
    def validate_atr_range(cls, v):
        """Ensure ATR multipliers are positive."""
        if Decimal(v) <= 0:
            raise ValueError("ATR multipliers must be positive")
        return Decimal(v)
    
    @field_validator("max_core_pct", "scale_out_pct", mode="before")
    @classmethod
    def validate_percentage(cls, v):
        """Ensure percentages are between 0 and 100."""
        val = Decimal(v)
        if not (0 < val <= 100):
            raise ValueError("Percentage must be between 0 and 100")
        return val


class Settings(BaseSettings):
    """
    Main application settings.
    
    Loads from environment variables and .env file.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # Application
    app_name: str = Field(default="IronHand SaaS", description="Application name")
    environment: str = Field(default="development", description="Environment (development, staging, production)")
    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="INFO", description="Log level")
    json_logs: bool = Field(default=True, description="Output JSON logs")
    
    # Component settings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    api: APISettings = Field(default_factory=APISettings)
    broker: BrokerSettings = Field(default_factory=BrokerSettings)
    strategy: StrategySettings = Field(default_factory=StrategySettings)


# Singleton instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get or create the global settings instance.
    
    Returns:
        Application settings
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

# Alias for compatibility
StrategyConfig = StrategySettings
