"""
server/jarvis_state.py — Jarvis State Manager (Singleton)

Tracks the assistant's real-time status and conversation history
so that REST endpoints and WebSocket clients can query it.

Thread-safe: all mutations go through a threading.Lock.
"""

import threading
from datetime import datetime


class JarvisState:
    """
    Singleton that holds Jarvis's current state.

    Attributes:
        status:    Current phase — idle / listening / thinking / speaking.
        last_query:    Most recent user query.
        last_response: Most recent Jarvis response.
        conversation_history: List of recent conversation messages.
        skills:    List of loaded skill names.
    """

    _instance: "JarvisState | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "JarvisState":
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

        self._state_lock = threading.Lock()
        self.status: str = "idle"
        self.last_query: str = ""
        self.last_response: str = ""
        self.conversation_history: list[dict] = []
        self.skills: list[str] = []
        self._start_time: str = datetime.now().isoformat()

    # ── Mutations ──────────────────────────────

    def update(self, **kwargs) -> None:
        """Update one or more state fields atomically."""
        with self._state_lock:
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)

    def add_message(self, role: str, content: str) -> None:
        """Append a message to conversation history (keeps last 20)."""
        with self._state_lock:
            self.conversation_history.append({
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat(),
            })
            # Keep only the last 20 messages
            if len(self.conversation_history) > 20:
                self.conversation_history = self.conversation_history[-20:]

    # ── Queries ────────────────────────────────

    def get_state(self) -> dict:
        """Return a snapshot of the full state as a dict."""
        with self._state_lock:
            return {
                "status": self.status,
                "last_query": self.last_query,
                "last_response": self.last_response,
                "skills": list(self.skills),
                "uptime_since": self._start_time,
            }

    def get_history(self, count: int = 10) -> list[dict]:
        """Return the last *count* conversation messages."""
        with self._state_lock:
            return list(self.conversation_history[-count:])
