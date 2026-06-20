"""
server/event_bus.py — Global Event Bus (Singleton)

Bridges synchronous code (main voice loop) with the async WebSocket
broadcast layer.  Uses ``asyncio.run_coroutine_threadsafe()`` so that
any thread can emit events without needing its own event loop.

Usage from main.py:
    from server.event_bus import event_bus
    event_bus.broadcast("listening", {})
"""

import asyncio
import json
import logging
import threading
from datetime import datetime

logger = logging.getLogger(__name__)


class EventBus:
    """
    Thread-safe singleton event bus.

    Call ``broadcast(event_type, data)`` from any thread — the event is
    forwarded to the async ``ConnectionManager.broadcast()`` in the
    FastAPI/uvicorn event loop.
    """

    _instance: "EventBus | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "EventBus":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True

        self._loop: asyncio.AbstractEventLoop | None = None
        self._manager = None  # set by app.py once the server starts

    # ── Called by app.py at startup ───────────

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Register the uvicorn/asyncio event loop."""
        self._loop = loop

    def set_manager(self, manager) -> None:
        """Register the WebSocket ConnectionManager."""
        self._manager = manager

    # ── Public API (callable from any thread) ─

    def broadcast(self, event_type: str, data: dict | None = None) -> None:
        """
        Emit an event to all connected WebSocket clients.

        Safe to call from the main voice-loop thread — the actual
        send is scheduled on the server's asyncio loop.
        """
        if self._loop is None or self._manager is None:
            return  # server not started yet — silently skip

        payload = {
            "event": event_type,
            "data": data or {},
            "timestamp": datetime.now().isoformat(),
        }

        try:
            asyncio.run_coroutine_threadsafe(
                self._manager.broadcast(payload),
                self._loop,
            )
        except Exception as e:
            logger.debug(f"EventBus broadcast failed: {e}")


# Module-level singleton for convenient imports
event_bus = EventBus()
