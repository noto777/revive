"""
Notification Dispatcher

Routes events from the event bus to tenant's configured notification channels.
Subscribes to event bus and dispatches to Telegram, webhooks, etc.
"""

from typing import Optional
from uuid import UUID

import structlog

from engine.events import BaseEvent, EventBus, EventType, get_event_bus
from .base import NotifierInterface
from .telegram import TelegramConfig, TelegramNotifier
from .webhook import WebhookConfig, WebhookNotifier

logger = structlog.get_logger()


class NotificationDispatcher:
    """
    Routes events to tenant-specific notification channels.
    
    Subscribes to the event bus and dispatches events to
    all configured channels for the tenant.
    """
    
    def __init__(self, event_bus: Optional[EventBus] = None):
        self.event_bus = event_bus or get_event_bus()
        
        # Tenant ID -> list of notifiers
        self._notifiers: dict[UUID, list[NotifierInterface]] = {}
        
        self.logger = logger.bind(component="notification_dispatcher")
    
    async def register_notifier(
        self,
        tenant_id: UUID,
        notifier: NotifierInterface
    ) -> None:
        """
        Register a notifier for a tenant.
        
        Args:
            tenant_id: Tenant UUID
            notifier: Notifier instance
        """
        if tenant_id not in self._notifiers:
            self._notifiers[tenant_id] = []
        
        self._notifiers[tenant_id].append(notifier)
        
        self.logger.info(
            "Notifier registered",
            tenant_id=str(tenant_id),
            notifier_type=notifier.config.channel_type,
            total_notifiers=len(self._notifiers[tenant_id])
        )
    
    async def unregister_notifier(
        self,
        tenant_id: UUID,
        notifier: NotifierInterface
    ) -> None:
        """
        Unregister a notifier.
        
        Args:
            tenant_id: Tenant UUID
            notifier: Notifier instance to remove
        """
        if tenant_id in self._notifiers:
            try:
                self._notifiers[tenant_id].remove(notifier)
                self.logger.info(
                    "Notifier unregistered",
                    tenant_id=str(tenant_id),
                    notifier_type=notifier.config.channel_type
                )
            except ValueError:
                self.logger.warning(
                    "Notifier not found",
                    tenant_id=str(tenant_id)
                )
    
    async def start(self) -> None:
        """
        Start dispatcher by subscribing to all event types.
        """
        # Subscribe to all event types
        for event_type in EventType:
            await self.event_bus.subscribe(event_type, self._handle_event)
        
        self.logger.info("Notification dispatcher started")
    
    async def stop(self) -> None:
        """
        Stop dispatcher and close all notifiers.
        """
        # Unsubscribe from event bus
        for event_type in EventType:
            await self.event_bus.unsubscribe(event_type, self._handle_event)
        
        # Close all notifiers
        for notifiers in self._notifiers.values():
            for notifier in notifiers:
                if hasattr(notifier, "close"):
                    await notifier.close()
        
        self._notifiers.clear()
        
        self.logger.info("Notification dispatcher stopped")
    
    async def _handle_event(self, event: BaseEvent) -> None:
        """
        Handle event from event bus.
        
        Dispatches to all notifiers configured for the tenant.
        
        Args:
            event: Event to dispatch
        """
        tenant_id = event.tenant_id
        
        notifiers = self._notifiers.get(tenant_id, [])
        
        if not notifiers:
            self.logger.debug(
                "No notifiers configured for tenant",
                tenant_id=str(tenant_id),
                event_type=event.event_type.value
            )
            return
        
        # Send to all notifiers
        for notifier in notifiers:
            if notifier.should_notify(event):
                try:
                    await notifier.send(event)
                except Exception as e:
                    self.logger.error(
                        "Notifier send failed",
                        tenant_id=str(tenant_id),
                        notifier_type=notifier.config.channel_type,
                        event_type=event.event_type.value,
                        error=str(e)
                    )
    
    def get_notifier_count(self, tenant_id: UUID) -> int:
        """
        Get number of notifiers for a tenant.
        
        Args:
            tenant_id: Tenant UUID
        
        Returns:
            Number of configured notifiers
        """
        return len(self._notifiers.get(tenant_id, []))


async def create_notifier_from_config(
    channel_type: str,
    config_dict: dict
) -> NotifierInterface:
    """
    Factory function to create notifier from config.
    
    Args:
        channel_type: Type of channel (telegram, webhook)
        config_dict: Configuration dictionary
    
    Returns:
        Notifier instance
    
    Raises:
        ValueError: If channel type is unknown
    """
    if channel_type == "telegram":
        config = TelegramConfig(**config_dict)
        return TelegramNotifier(config)
    
    elif channel_type == "webhook":
        config = WebhookConfig(**config_dict)
        return WebhookNotifier(config)
    
    else:
        raise ValueError(f"Unknown channel type: {channel_type}")
