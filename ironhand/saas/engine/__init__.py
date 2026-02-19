"""
Strategy execution engine package.

Contains:
- executor.py: Per-tenant strategy loop (replaces main.py) ✅
- scheduler.py: Manages executor lifecycle across tenants (TODO)
- signals.py: Graceful shutdown handlers ✅
- events.py: Internal event bus ✅
"""

from .signals import ShutdownManager, get_shutdown_manager
from .executor import StrategyExecutor
from .events import get_event_bus, EventBus, EventType

__all__ = [
    "ShutdownManager",
    "get_shutdown_manager",
    "StrategyExecutor",
    "get_event_bus",
    "EventBus",
    "EventType",
]
