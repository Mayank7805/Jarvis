"""
skills/timer.py — Timer & Alarm Skill

Sets non-blocking background timers using ``threading.Timer``.
When a timer fires it plays a beep sound via ``sounddevice`` + ``numpy``
(both already installed in the project).

Parses natural-language durations:
    "set timer for 5 minutes"  → 300 s
    "remind me in 30 seconds"  → 30 s
    "timer 1 hour"             → 3600 s
    "after 2 and a half minutes" → 150 s
"""

import re
import threading
import time

import numpy as np
import sounddevice as sd

from skills.base_skill import BaseSkill
from server.event_bus import event_bus


# Keep references so timers aren't garbage-collected
_active_timers: list[threading.Timer] = []


class TimerSkill(BaseSkill):
    """Sets non-blocking background timers with audible alerts."""

    @property
    def name(self) -> str:
        return "Timer"

    @property
    def keywords(self) -> list[str]:
        return ["timer", "alarm", "remind me in", "after"]

    def can_handle(self, query: str) -> bool:
        """
        Override base matching to reduce false positives.

        "after" is too generic alone — require a time unit nearby.
        """
        q = query.lower()

        # Direct keywords are always fine
        if any(kw in q for kw in ("timer", "alarm", "remind me in")):
            return True

        # "after" needs a time unit to be a timer request
        if "after" in q:
            return bool(re.search(r"\d+\s*(second|minute|hour|sec|min|hr)", q))

        return False

    def execute(self, query: str) -> str:
        """Parse duration from query and start a background timer."""
        seconds = self._parse_time(query)
        if seconds is None or seconds <= 0:
            return "I couldn't figure out the duration. Try saying set timer for 5 minutes."

        label = self._extract_label(query)
        self._start_timer(seconds, label)

        # Broadcast timer start to World Monitor
        event_bus.broadcast("content_update", {
            "type": "timer",
            "payload": {
                "duration_seconds": seconds,
                "remaining_seconds": seconds,
                "label": label,
                "fired": False,
            },
        })

        return self._format_confirmation(seconds, label)

    # ── Timer Engine ───────────────────────────

    @staticmethod
    def _start_timer(seconds: float, label: str) -> None:
        """
        Launch a non-blocking timer that plays a beep when done.

        Also starts a countdown broadcast thread that sends remaining
        seconds to the World Monitor UI every second.
        """
        def _on_fire():
            print(f"\n🔔  Timer fired! {label}")
            # Broadcast timer fired
            event_bus.broadcast("content_update", {
                "type": "timer",
                "payload": {
                    "duration_seconds": seconds,
                    "remaining_seconds": 0,
                    "label": label,
                    "fired": True,
                },
            })
            TimerSkill._play_alarm()
            # Revert to idle after 5 seconds
            time.sleep(5)
            event_bus.broadcast("content_update", {"type": "idle", "payload": {}})

        def _countdown():
            """Broadcast remaining time to the UI every second."""
            remaining = int(seconds)
            while remaining > 0:
                time.sleep(1)
                remaining -= 1
                event_bus.broadcast("content_update", {
                    "type": "timer",
                    "payload": {
                        "duration_seconds": seconds,
                        "remaining_seconds": remaining,
                        "label": label,
                        "fired": False,
                    },
                })

        t = threading.Timer(seconds, _on_fire)
        t.daemon = True
        t.start()
        _active_timers.append(t)

        # Start countdown broadcast thread
        ct = threading.Thread(target=_countdown, daemon=True)
        ct.start()

    @staticmethod
    def _play_alarm(
        frequency: int = 1000,
        duration: float = 0.3,
        repeats: int = 3,
        sample_rate: int = 16000,
    ) -> None:
        """Play a repeating beep pattern as an alarm."""
        t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
        tone = (0.6 * np.sin(2 * np.pi * frequency * t)).astype(np.float32)
        silence = np.zeros(int(sample_rate * 0.15), dtype=np.float32)

        # Build the pattern: beep-pause-beep-pause-beep
        pattern = np.concatenate(
            [np.concatenate([tone, silence]) for _ in range(repeats)]
        )
        sd.play(pattern, samplerate=sample_rate)
        sd.wait()

    # ── Parsing ────────────────────────────────

    @staticmethod
    def _parse_time(query: str) -> float | None:
        """
        Extract duration in seconds from natural language.

        Handles:
            "5 minutes"             → 300
            "30 seconds"            → 30
            "1 hour"                → 3600
            "2 hours 30 minutes"    → 9000
            "1 and a half minutes"  → 90
            "90 seconds"            → 90
        """
        q = query.lower()
        total_seconds = 0.0
        found = False

        # Handle "and a half" / "and half"
        q = re.sub(r"and\s+a\s+half", "30", q)
        q = re.sub(r"and\s+half", "30", q)

        # Match all number + unit pairs
        patterns = [
            (r"(\d+(?:\.\d+)?)\s*(?:hour|hr)s?", 3600),
            (r"(\d+(?:\.\d+)?)\s*(?:minute|min)s?", 60),
            (r"(\d+(?:\.\d+)?)\s*(?:second|sec)s?", 1),
        ]

        for pattern, multiplier in patterns:
            for match in re.finditer(pattern, q):
                total_seconds += float(match.group(1)) * multiplier
                found = True

        return total_seconds if found else None

    @staticmethod
    def _extract_label(query: str) -> str:
        """Extract a human label, or default to 'Timer'."""
        # Try to find text after "for" that isn't a number
        match = re.search(r"(?:for|to)\s+(.+?)(?:\s+(?:in|after|timer|alarm).*)?$", query, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            # If it's just a duration, use default
            if not re.match(r"^\d+\s*(second|minute|hour|sec|min|hr)", candidate):
                return candidate
        return "Timer"

    @staticmethod
    def _format_confirmation(seconds: float, label: str) -> str:
        """Build a voice-friendly confirmation string."""
        parts = []
        hrs = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hrs:
            parts.append(f"{hrs} hour{'s' if hrs != 1 else ''}")
        if mins:
            parts.append(f"{mins} minute{'s' if mins != 1 else ''}")
        if secs:
            parts.append(f"{secs} second{'s' if secs != 1 else ''}")

        duration_str = " and ".join(parts) if parts else "0 seconds"
        label_suffix = f" for {label}" if label != "Timer" else ""

        return f"Timer set for {duration_str}{label_suffix}."
