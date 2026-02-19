# app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Revive - Stripe Recovery"
    DATABASE_URL: str = "sqlite+aiosqlite:///./revive.db"
    STRIPE_API_KEY: str = "sk_test_mock"
    STRIPE_WEBHOOK_SECRET: str = "whsec_mock"
    STRIPE_API_VERSION: str = "2025-01-30.acacia"
    REDIS_URL: str = "redis://localhost:6379/0"
    RESEND_API_KEY: str = "re_mock"
    FROM_EMAIL: str = "onboarding@resend.dev"
    DASHBOARD_USER: str = "admin"
    DASHBOARD_PASS: str = "revive2025"

    class Config:
        env_file = ".env"

settings = Settings()
