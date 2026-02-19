"""
Graceful Shutdown Signal Handling

Captures SIGTERM and SIGINT for clean shutdown.
Allows executors to finish current cycle and disconnect cleanly.

Replaces the naked time.sleep(15) loops with proper async wait.
"""

import asyncio
import signal
from typing import Optional

from logger import get_logger

logger = get_logger()


class ShutdownManager:
    """
    Manages graceful shutdown signals.
    
    Sets an event when SIGTERM or SIGINT is received,
    allowing running tasks to check and exit cleanly.
    
    Usage:
        >>> shutdown = ShutdownManager()
        >>> while not shutdown.should_shutdown():
        ...     await do_work()
        ...     await shutdown.wait_or_shutdown(timeout=15)
    """
    
    def __init__(self):
        """Initialize shutdown manager and register signal handlers."""
        self._shutdown_event = asyncio.Event()
        self._original_handlers = {}
        
        # Register handlers for both SIGTERM (kill/systemd) and SIGINT (Ctrl+C)
        self._register_signal_handler(signal.SIGTERM)
        self._register_signal_handler(signal.SIGINT)
        
        logger.info("shutdown_manager_initialized", signals=["SIGTERM", "SIGINT"])
    
    def _register_signal_handler(self, sig: signal.Signals):
        """
        Register handler for a specific signal.
        
        Args:
            sig: Signal to handle
        """
        # Save original handler
        self._original_handlers[sig] = signal.getsignal(sig)
        
        # Set new handler
        signal.signal(sig, self._handle_signal)
    
    def _handle_signal(self, signum: int, frame):
        """
        Signal handler callback.
        
        Args:
            signum: Signal number
            frame: Current stack frame
        """
        sig_name = signal.Signals(signum).name
        logger.warning("shutdown_signal_received", signal=sig_name)
        
        # Set the shutdown event
        self._shutdown_event.set()
    
    def trigger_shutdown(self):
        """Manually trigger shutdown event."""
        logger.info("manual_shutdown_triggered")
        self._shutdown_event.set()
    
    def should_shutdown(self) -> bool:
        """
        Check if shutdown has been requested.
        
        Returns:
            True if shutdown signal received, False otherwise
        """
        return self._shutdown_event.is_set()
    
    async def wait_or_shutdown(self, timeout: float) -> bool:
        """
        Wait for timeout or shutdown signal, whichever comes first.
        
        This replaces time.sleep() in the main loop, allowing
        immediate response to shutdown signals.
        
        Args:
            timeout: Maximum seconds to wait
            
        Returns:
            True if shutdown requested, False if timeout elapsed
            
        Example:
            >>> while True:
            ...     if await shutdown.wait_or_shutdown(15):
            ...         break  # Shutdown requested
            ...     # Continue with work
        """
        try:
            await asyncio.wait_for(
                self._shutdown_event.wait(),
                timeout=timeout
            )
            # Event was set (shutdown)
            return True
        except asyncio.TimeoutError:
            # Timeout elapsed (normal operation)
            return False
    
    async def wait(self):
        """
        Wait indefinitely until shutdown is requested.
        
        Useful for keeping a service running until termination.
        
        Example:
            >>> await shutdown.wait()
            >>> logger.info("Shutting down...")
        """
        await self._shutdown_event.wait()
    
    def restore_handlers(self):
        """
        Restore original signal handlers.
        
        Call this during cleanup to avoid interfering with other code.
        """
        for sig, handler in self._original_handlers.items():
            signal.signal(sig, handler)
        
        logger.debug("signal_handlers_restored")


# Global singleton instance
_shutdown_manager: Optional[ShutdownManager] = None


def get_shutdown_manager() -> ShutdownManager:
    """
    Get or create the global shutdown manager instance.
    
    Returns:
        ShutdownManager singleton
    """
    global _shutdown_manager
    if _shutdown_manager is None:
        _shutdown_manager = ShutdownManager()
    return _shutdown_manager
