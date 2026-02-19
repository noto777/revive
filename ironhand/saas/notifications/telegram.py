"""
Telegram Notification Channel

Sends notifications via Telegram bot.
Extracted from the monolith's Telegram integration.
"""

import asyncio
from dataclasses import dataclass
from typing import Optional

import httpx
import structlog

from engine.events import BaseEvent, EventType
from .base import NotificationConfig, NotifierInterface

logger = structlog.get_logger()


@dataclass
class TelegramConfig(NotificationConfig):
    """Telegram-specific configuration."""
    
    bot_token: str
    chat_id: str
    parse_mode: str = "Markdown"  # Markdown or HTML
    disable_notifications: bool = False
    
    def __post_init__(self):
        self.channel_type = "telegram"


class TelegramNotifier(NotifierInterface):
    """
    Telegram notification implementation.
    
    Uses Telegram Bot API to send messages to a specific chat.
    """
    
    def __init__(self, config: TelegramConfig):
        super().__init__(config)
        self.config: TelegramConfig = config
        self._base_url = f"https://api.telegram.org/bot{config.bot_token}"
        self._client = httpx.AsyncClient(timeout=10.0)
    
    async def send(self, event: BaseEvent, message: Optional[str] = None) -> bool:
        """Send notification via Telegram."""
        if not self.should_notify(event):
            return False
        
        # Use provided message or format from event
        text = message or self.format_message(event)
        
        # Send to Telegram
        url = f"{self._base_url}/sendMessage"
        payload = {
            "chat_id": self.config.chat_id,
            "text": text,
            "parse_mode": self.config.parse_mode,
            "disable_notification": self.config.disable_notifications
        }
        
        try:
            response = await self._client.post(url, json=payload)
            response.raise_for_status()
            
            self.logger.info(
                "Telegram notification sent",
                event_type=event.event_type.value,
                chat_id=self.config.chat_id
            )
            return True
            
        except Exception as e:
            self.logger.error(
                "Failed to send Telegram notification",
                error=str(e),
                event_type=event.event_type.value
            )
            return False
    
    async def test_connection(self) -> bool:
        """Test Telegram bot connection."""
        url = f"{self._base_url}/getMe"
        
        try:
            response = await self._client.get(url)
            response.raise_for_status()
            data = response.json()
            
            if data.get("ok"):
                bot_info = data.get("result", {})
                self.logger.info(
                    "Telegram connection test successful",
                    bot_username=bot_info.get("username")
                )
                return True
            else:
                self.logger.error("Telegram API returned error", data=data)
                return False
                
        except Exception as e:
            self.logger.error("Telegram connection test failed", error=str(e))
            return False
    
    def format_message(self, event: BaseEvent) -> str:
        """Format event as Telegram message with Markdown."""
        data = event.to_dict()
        
        # Icon mapping for different event types
        icon_map = {
            EventType.ORDER_FILLED: "✅",
            EventType.ORDER_PLACED: "📤",
            EventType.ORDER_CANCELLED: "❌",
            EventType.ORDER_REJECTED: "🚫",
            EventType.ORDER_ERROR: "⚠️",
            EventType.POSITION_OPENED: "🟢",
            EventType.POSITION_CLOSED: "🔴",
            EventType.LADDER_PLACED: "📊",
            EventType.STRATEGY_STARTED: "▶️",
            EventType.STRATEGY_STOPPED: "⏹️",
            EventType.STRATEGY_PAUSED: "⏸️",
            EventType.STRATEGY_ERROR: "💥",
            EventType.CORE_REBALANCE: "⚖️",
            EventType.PROFIT_LOCK_TRIGGERED: "🔒",
        }
        
        icon = icon_map.get(event.event_type, "🔔")
        title = event.event_type.value.replace("_", " ").title()
        
        # Build message with Markdown formatting
        lines = [
            f"{icon} *{title}*",
            f"",
            f"Symbol: `{event.symbol}`",
            f"Time: {event.timestamp.strftime('%H:%M:%S UTC')}",
        ]
        
        # Add event-specific details
        exclude_keys = {
            "event_type", "symbol", "timestamp", "tenant_id", 
            "strategy_id", "error_type", "old_status", "new_status"
        }
        
        for key, value in data.items():
            if key not in exclude_keys and value is not None:
                label = key.replace("_", " ").title()
                
                # Special formatting for certain fields
                if "price" in key or "pnl" in key or "value" in key:
                    lines.append(f"{label}: `${value}`")
                elif "quantity" in key or "qty" in key:
                    lines.append(f"{label}: `{value}`")
                elif key == "status":
                    lines.append(f"{label}: *{value.upper()}*")
                else:
                    lines.append(f"{label}: {value}")
        
        # Add error message if present
        if hasattr(event, "error_message") and event.error_message:
            lines.append(f"")
            lines.append(f"Error: `{event.error_message}`")
        
        # Add status transition if present
        if hasattr(event, "old_status") and hasattr(event, "new_status"):
            lines.append(f"")
            lines.append(f"Status: {event.old_status} → *{event.new_status}*")
        
        return "\n".join(lines)
    
    async def close(self):
        """Close HTTP client."""
        await self._client.aclose()
