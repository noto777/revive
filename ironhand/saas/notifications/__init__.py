"""
Notification Abstraction Layer

Multi-channel notification system for strategy events.
Supports Telegram, webhooks (Slack, Discord), and custom endpoints.
"""

from .base import NotificationConfig, NotifierInterface
from .dispatcher import NotificationDispatcher, create_notifier_from_config
from .telegram import TelegramConfig, TelegramNotifier
from .webhook import WebhookConfig, WebhookNotifier

__all__ = [
    # Base
    "NotificationConfig",
    "NotifierInterface",
    # Implementations
    "TelegramConfig",
    "TelegramNotifier",
    "WebhookConfig",
    "WebhookNotifier",
    # Dispatcher
    "NotificationDispatcher",
    "create_notifier_from_config",
]
