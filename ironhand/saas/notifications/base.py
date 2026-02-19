"""
Abstract Notification Interface

Base class for notification channel implementations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

import structlog

from engine.events import BaseEvent, EventType

logger = structlog.get_logger()


@dataclass
class NotificationConfig:
    """Base notification configuration."""
    
    channel_type: str
    enabled: bool = True
    event_filters: Optional[list[EventType]] = None  # None = all events


class NotifierInterface(ABC):
    """
    Abstract notifier interface.
    
    All notification implementations (Telegram, Webhook, Email, etc.)
    must implement these methods.
    """
    
    def __init__(self, config: NotificationConfig):
        self.config = config
        self.logger = logger.bind(notifier=config.channel_type)
    
    @abstractmethod
    async def send(self, event: BaseEvent, message: str) -> bool:
        """
        Send a notification.
        
        Args:
            event: Event that triggered the notification
            message: Formatted message to send
        
        Returns:
            True if sent successfully, False otherwise
        """
        pass
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """
        Test if the notification channel is reachable.
        
        Returns:
            True if connection successful, False otherwise
        """
        pass
    
    def should_notify(self, event: BaseEvent) -> bool:
        """
        Check if this notifier should handle the event.
        
        Args:
            event: Event to check
        
        Returns:
            True if should notify, False otherwise
        """
        if not self.config.enabled:
            return False
        
        # If no filters, notify for all events
        if not self.config.event_filters:
            return True
        
        # Check if event type is in filter list
        return event.event_type in self.config.event_filters
    
    def format_message(self, event: BaseEvent) -> str:
        """
        Format event into a message string.
        
        Default implementation creates a basic text message.
        Override for custom formatting (e.g., Markdown, HTML).
        
        Args:
            event: Event to format
        
        Returns:
            Formatted message string
        """
        data = event.to_dict()
        
        # Build message
        lines = [
            f"🔔 **{event.event_type.value.upper().replace('_', ' ')}**",
            f"Symbol: {event.symbol}",
            f"Time: {event.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        ]
        
        # Add event-specific details
        for key, value in data.items():
            if key not in ("event_type", "symbol", "timestamp", "tenant_id", "strategy_id"):
                if value is not None:
                    lines.append(f"{key.replace('_', ' ').title()}: {value}")
        
        return "\n".join(lines)
