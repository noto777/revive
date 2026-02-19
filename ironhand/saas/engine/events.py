"""
Internal Event Bus

Pub/sub event system for strategy lifecycle events.
Executors publish events, notifications and websockets subscribe.
Fully async-compatible for multi-tenant operation.
"""

import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Optional
from uuid import UUID

import structlog

logger = structlog.get_logger()


class EventType(str, Enum):
    """Event types published by the strategy executor."""
    
    # Order events
    ORDER_PLACED = "order_placed"
    ORDER_FILLED = "order_filled"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_REJECTED = "order_rejected"
    ORDER_ERROR = "order_error"
    
    # Position events
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    POSITION_UPDATED = "position_updated"
    
    # Strategy events
    LADDER_PLACED = "ladder_placed"
    LADDER_UPDATED = "ladder_updated"
    
    # Status events
    STRATEGY_STARTED = "strategy_started"
    STRATEGY_STOPPED = "strategy_stopped"
    STRATEGY_PAUSED = "strategy_paused"
    STRATEGY_RESUMED = "strategy_resumed"
    STRATEGY_ERROR = "strategy_error"
    
    # Core management events
    CORE_REBALANCE = "core_rebalance"
    CORE_SCALE_OUT = "core_scale_out"
    PROFIT_LOCK_ARMED = "profit_lock_armed"
    PROFIT_LOCK_TRIGGERED = "profit_lock_triggered"


@dataclass
class BaseEvent:
    """Base event class with common fields."""
    
    event_type: EventType
    tenant_id: UUID
    strategy_id: UUID
    symbol: str
    timestamp: datetime
    
    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary for serialization."""
        data = asdict(self)
        # Convert UUIDs and datetimes to strings
        data["tenant_id"] = str(data["tenant_id"])
        data["strategy_id"] = str(data["strategy_id"])
        data["timestamp"] = data["timestamp"].isoformat()
        data["event_type"] = self.event_type.value
        return data


@dataclass
class OrderEvent(BaseEvent):
    """Order-related event."""
    
    broker_order_id: str
    side: str  # BUY, SELL
    order_type: str  # MKT, LMT, STP
    quantity: Decimal
    limit_price: Optional[Decimal] = None
    fill_price: Optional[Decimal] = None
    status: Optional[str] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        if self.quantity:
            data["quantity"] = str(self.quantity)
        if self.limit_price:
            data["limit_price"] = str(self.limit_price)
        if self.fill_price:
            data["fill_price"] = str(self.fill_price)
        return data


@dataclass
class PositionEvent(BaseEvent):
    """Position-related event."""
    
    position_id: UUID
    side: str  # LONG, SHORT
    quantity: Decimal
    entry_price: Decimal
    exit_price: Optional[Decimal] = None
    pnl: Optional[Decimal] = None
    rung_index: Optional[int] = None
    
    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["position_id"] = str(self.position_id)
        if self.quantity:
            data["quantity"] = str(self.quantity)
        if self.entry_price:
            data["entry_price"] = str(self.entry_price)
        if self.exit_price:
            data["exit_price"] = str(self.exit_price)
        if self.pnl:
            data["pnl"] = str(self.pnl)
        return data


@dataclass
class LadderEvent(BaseEvent):
    """Ladder placement/update event."""
    
    num_rungs: int
    start_price: Decimal
    end_price: Decimal
    total_value: Decimal
    atr: Decimal
    
    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["start_price"] = str(self.start_price)
        data["end_price"] = str(self.end_price)
        data["total_value"] = str(self.total_value)
        data["atr"] = str(self.atr)
        return data


@dataclass
class StatusEvent(BaseEvent):
    """Strategy status change event."""
    
    old_status: str
    new_status: str
    message: Optional[str] = None


@dataclass
class ErrorEvent(BaseEvent):
    """Error event."""
    
    error_type: str
    error_message: str
    stack_trace: Optional[str] = None


@dataclass
class CoreManagementEvent(BaseEvent):
    """Core position management event."""
    
    action: str  # rebalance, scale_out, profit_lock_armed, profit_lock_triggered
    current_core_pct: Decimal
    target_core_pct: Optional[Decimal] = None
    profit_pct: Optional[Decimal] = None
    sell_quantity: Optional[Decimal] = None
    
    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["current_core_pct"] = str(self.current_core_pct)
        if self.target_core_pct:
            data["target_core_pct"] = str(self.target_core_pct)
        if self.profit_pct:
            data["profit_pct"] = str(self.profit_pct)
        if self.sell_quantity:
            data["sell_quantity"] = str(self.sell_quantity)
        return data


class EventBus:
    """
    Async event bus for pub/sub messaging.
    
    Subscribers register callbacks for event types.
    Publishers emit events that are dispatched to all matching subscribers.
    Thread-safe and async-compatible.
    """
    
    def __init__(self):
        self._subscribers: dict[EventType, list[Callable[[BaseEvent], Any]]] = {}
        self._lock = asyncio.Lock()
        self.logger = logger.bind(component="event_bus")
    
    async def subscribe(
        self,
        event_type: EventType,
        callback: Callable[[BaseEvent], Any]
    ) -> None:
        """
        Subscribe to an event type.
        
        Args:
            event_type: Type of event to subscribe to
            callback: Async or sync function to call when event is published
                     Signature: callback(event: BaseEvent) -> Any
        """
        async with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            
            self._subscribers[event_type].append(callback)
            
            self.logger.info(
                "Subscriber registered",
                event_type=event_type.value,
                total_subscribers=len(self._subscribers[event_type])
            )
    
    async def unsubscribe(
        self,
        event_type: EventType,
        callback: Callable[[BaseEvent], Any]
    ) -> None:
        """
        Unsubscribe from an event type.
        
        Args:
            event_type: Type of event to unsubscribe from
            callback: Callback function to remove
        """
        async with self._lock:
            if event_type in self._subscribers:
                try:
                    self._subscribers[event_type].remove(callback)
                    self.logger.info(
                        "Subscriber removed",
                        event_type=event_type.value,
                        remaining=len(self._subscribers[event_type])
                    )
                except ValueError:
                    self.logger.warning(
                        "Callback not found in subscribers",
                        event_type=event_type.value
                    )
    
    async def publish(self, event: BaseEvent) -> None:
        """
        Publish an event to all subscribers.
        
        Args:
            event: Event to publish
        """
        event_type = event.event_type
        
        async with self._lock:
            subscribers = self._subscribers.get(event_type, []).copy()
        
        if not subscribers:
            self.logger.debug(
                "No subscribers for event",
                event_type=event_type.value
            )
            return
        
        self.logger.info(
            "Publishing event",
            event_type=event_type.value,
            subscriber_count=len(subscribers),
            tenant_id=str(event.tenant_id),
            strategy_id=str(event.strategy_id)
        )
        
        # Dispatch to all subscribers (async or sync)
        for callback in subscribers:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                self.logger.error(
                    "Subscriber callback failed",
                    event_type=event_type.value,
                    error=str(e),
                    exc_info=True
                )
    
    async def publish_many(self, events: list[BaseEvent]) -> None:
        """
        Publish multiple events.
        
        Args:
            events: List of events to publish
        """
        for event in events:
            await self.publish(event)
    
    def subscriber_count(self, event_type: EventType) -> int:
        """
        Get number of subscribers for an event type.
        
        Args:
            event_type: Event type to check
        
        Returns:
            Number of subscribers
        """
        return len(self._subscribers.get(event_type, []))
    
    async def clear_subscribers(self, event_type: Optional[EventType] = None) -> None:
        """
        Clear all subscribers (or for a specific event type).
        
        Args:
            event_type: Event type to clear (None = clear all)
        """
        async with self._lock:
            if event_type is None:
                self._subscribers.clear()
                self.logger.info("All subscribers cleared")
            else:
                self._subscribers.pop(event_type, None)
                self.logger.info(
                    "Subscribers cleared",
                    event_type=event_type.value
                )


# Global event bus instance
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """
    Get or create the global event bus instance.
    
    Returns:
        Global event bus
    """
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus
