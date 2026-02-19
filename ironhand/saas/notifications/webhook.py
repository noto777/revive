"""
Webhook Notification Channel

Sends notifications to generic webhooks (Slack, Discord, custom endpoints).
"""

from dataclasses import dataclass
from typing import Any, Optional

import httpx
import structlog

from engine.events import BaseEvent
from .base import NotificationConfig, NotifierInterface

logger = structlog.get_logger()


@dataclass
class WebhookConfig(NotificationConfig):
    """Webhook-specific configuration."""
    
    url: str
    method: str = "POST"
    headers: Optional[dict[str, str]] = None
    auth_token: Optional[str] = None
    format: str = "json"  # json, slack, discord
    
    def __post_init__(self):
        self.channel_type = "webhook"
        if self.headers is None:
            self.headers = {}


class WebhookNotifier(NotifierInterface):
    """
    Generic webhook notification implementation.
    
    Supports:
    - Plain JSON webhooks
    - Slack webhooks
    - Discord webhooks
    - Custom endpoints with auth
    """
    
    def __init__(self, config: WebhookConfig):
        super().__init__(config)
        self.config: WebhookConfig = config
        self._client = httpx.AsyncClient(timeout=10.0)
    
    async def send(self, event: BaseEvent, message: Optional[str] = None) -> bool:
        """Send notification to webhook."""
        if not self.should_notify(event):
            return False
        
        # Format payload based on webhook type
        payload = self._format_payload(event, message)
        
        # Prepare headers
        headers = self.config.headers.copy()
        if self.config.auth_token:
            headers["Authorization"] = f"Bearer {self.config.auth_token}"
        
        try:
            if self.config.method.upper() == "POST":
                response = await self._client.post(
                    self.config.url,
                    json=payload,
                    headers=headers
                )
            elif self.config.method.upper() == "PUT":
                response = await self._client.put(
                    self.config.url,
                    json=payload,
                    headers=headers
                )
            else:
                raise ValueError(f"Unsupported HTTP method: {self.config.method}")
            
            response.raise_for_status()
            
            self.logger.info(
                "Webhook notification sent",
                event_type=event.event_type.value,
                url=self.config.url,
                status_code=response.status_code
            )
            return True
            
        except Exception as e:
            self.logger.error(
                "Failed to send webhook notification",
                error=str(e),
                event_type=event.event_type.value,
                url=self.config.url
            )
            return False
    
    async def test_connection(self) -> bool:
        """Test webhook connection."""
        # Send a test ping
        test_payload = {
            "event": "test",
            "message": "IronHand SaaS webhook test"
        }
        
        try:
            headers = self.config.headers.copy()
            if self.config.auth_token:
                headers["Authorization"] = f"Bearer {self.config.auth_token}"
            
            response = await self._client.post(
                self.config.url,
                json=test_payload,
                headers=headers
            )
            
            # Consider 2xx and 404 as success (404 means endpoint exists but doesn't accept test)
            if response.status_code < 300 or response.status_code == 404:
                self.logger.info(
                    "Webhook connection test successful",
                    url=self.config.url,
                    status_code=response.status_code
                )
                return True
            else:
                self.logger.warning(
                    "Webhook connection test returned non-2xx",
                    url=self.config.url,
                    status_code=response.status_code
                )
                return False
                
        except Exception as e:
            self.logger.error(
                "Webhook connection test failed",
                error=str(e),
                url=self.config.url
            )
            return False
    
    def _format_payload(self, event: BaseEvent, message: Optional[str] = None) -> dict[str, Any]:
        """Format event as webhook payload."""
        event_data = event.to_dict()
        
        if self.config.format == "slack":
            return self._format_slack(event, event_data, message)
        elif self.config.format == "discord":
            return self._format_discord(event, event_data, message)
        else:
            # Plain JSON format
            return {
                "event": event.event_type.value,
                "data": event_data,
                "message": message or self.format_message(event)
            }
    
    def _format_slack(
        self,
        event: BaseEvent,
        event_data: dict[str, Any],
        message: Optional[str] = None
    ) -> dict[str, Any]:
        """Format for Slack webhook."""
        text = message or self.format_message(event)
        
        # Slack attachment with fields
        fields = []
        for key, value in event_data.items():
            if key not in ("event_type", "tenant_id", "strategy_id", "timestamp"):
                if value is not None:
                    fields.append({
                        "title": key.replace("_", " ").title(),
                        "value": str(value),
                        "short": len(str(value)) < 30
                    })
        
        return {
            "text": f"*{event.event_type.value.replace('_', ' ').title()}*",
            "attachments": [
                {
                    "color": self._get_color(event),
                    "text": text,
                    "fields": fields,
                    "footer": "IronHand SaaS",
                    "ts": int(event.timestamp.timestamp())
                }
            ]
        }
    
    def _format_discord(
        self,
        event: BaseEvent,
        event_data: dict[str, Any],
        message: Optional[str] = None
    ) -> dict[str, Any]:
        """Format for Discord webhook."""
        description = message or self.format_message(event)
        
        # Discord embed fields
        fields = []
        for key, value in event_data.items():
            if key not in ("event_type", "tenant_id", "strategy_id", "timestamp"):
                if value is not None:
                    fields.append({
                        "name": key.replace("_", " ").title(),
                        "value": str(value),
                        "inline": True
                    })
        
        return {
            "embeds": [
                {
                    "title": event.event_type.value.replace("_", " ").title(),
                    "description": description,
                    "color": int(self._get_color(event).replace("#", ""), 16),
                    "fields": fields,
                    "timestamp": event.timestamp.isoformat(),
                    "footer": {
                        "text": "IronHand SaaS"
                    }
                }
            ]
        }
    
    def _get_color(self, event: BaseEvent) -> str:
        """Get color for event type (hex)."""
        from engine.events import EventType
        
        color_map = {
            EventType.ORDER_FILLED: "#00FF00",
            EventType.ORDER_CANCELLED: "#FF0000",
            EventType.ORDER_ERROR: "#FF6600",
            EventType.POSITION_OPENED: "#00CC00",
            EventType.POSITION_CLOSED: "#CC0000",
            EventType.STRATEGY_STARTED: "#0099FF",
            EventType.STRATEGY_STOPPED: "#999999",
            EventType.STRATEGY_ERROR: "#FF0000",
            EventType.PROFIT_LOCK_TRIGGERED: "#FFD700",
        }
        
        return color_map.get(event.event_type, "#808080")
    
    async def close(self):
        """Close HTTP client."""
        await self._client.aclose()
