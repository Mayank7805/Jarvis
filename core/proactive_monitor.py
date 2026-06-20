"""
core/proactive_monitor.py — Proactive Context Monitor

Runs in a background daemon thread.  Checks system conditions every
60 seconds and speaks alerts via TTS when thresholds are breached.

Features:
  • Per-alert cooldown system to prevent spam
  • Conversation-aware — never interrupts active speech or conversation
  • Queue-and-retry — if busy, retries after 30 seconds
  • WebSocket broadcast for every alert (UI banner)
  • Time-based check-ins (morning, afternoon, evening)
  • Break reminder after 3+ hours of continuous use
"""

import time
import logging
import threading
from datetime import datetime

import psutil

logger = logging.getLogger(__name__)


class ProactiveMonitor:
    """
    Background monitor that checks system state and speaks proactive
    alerts through TTS when conditions warrant.

    Args:
        tts:          The TTS engine instance (must have .speak() and .is_speaking).
        event_bus:    The EventBus singleton for WebSocket broadcasts.
        jarvis_state: Shared dict with conversation-awareness flags:
                      {"is_speaking", "is_listening", "in_conversation", "conversation_start"}
    """

    def __init__(self, tts, event_bus, jarvis_state: dict) -> None:
        self.tts = tts
        self.event_bus = event_bus
        self.jarvis_state = jarvis_state

        # Cooldown tracking: alert_type → last_triggered_timestamp
        self._cooldowns: dict[str, float] = {}

        # Per-type cooldown durations (seconds)
        self._cooldown_durations: dict[str, int] = {
            "battery_low": 600,           # 10 minutes
            "battery_critical": 300,      # 5 minutes
            "battery_full": 86400,        # once per day (effectively once per session)
            "ram_high": 300,              # 5 minutes
            "ram_critical": 300,          # 5 minutes
            "cpu_high": 180,              # 3 minutes
            "break_reminder": 10800,      # 3 hours
            "midnight_alert": 86400,      # once per day
            "morning_checkin": 86400,     # once per day
            "afternoon_checkin": 86400,   # once per day
            "evening_checkin": 86400,     # once per day
        }

        # Session tracking
        self._session_start: float = time.time()
        self._last_break_reset: float = time.time()

        # CPU sustained-high tracking (need 3 consecutive checks ≥85%)
        self._cpu_high_streak: int = 0

        # Stop event for clean shutdown
        self._stop_event = threading.Event()

        # Timestamp of the last proactive alert spoken (max 1 per minute)
        self._last_alert_spoken: float = 0.0

        # Alert queue: list of (message, alert_type, severity) waiting to be spoken
        self._alert_queue: list[tuple[str, str, str]] = []
        self._queue_lock = threading.Lock()

    # ──────────────────────────────────────────
    #  Public API
    # ──────────────────────────────────────────

    def start(self) -> None:
        """
        Main loop — runs every 60 seconds until stop() is called.
        This is the target for the daemon thread.
        """
        logger.info("ProactiveMonitor started.")
        print("👁️  Proactive Monitor: ONLINE")

        # Wait a bit after startup before first check cycle
        # (let all modules finish initializing)
        self._stop_event.wait(timeout=30)

        while not self._stop_event.is_set():
            try:
                self._run_checks()
            except Exception as e:
                logger.error(f"ProactiveMonitor check cycle error: {e}")

            # Process any queued alerts that were delayed
            self._process_queue()

            # Sleep in 5-second increments so stop() is responsive
            for _ in range(12):  # 12 × 5s = 60s
                if self._stop_event.is_set():
                    break
                self._stop_event.wait(timeout=5)

        logger.info("ProactiveMonitor stopped.")

    def stop(self) -> None:
        """Signal the monitor to stop cleanly."""
        self._stop_event.set()

    # ──────────────────────────────────────────
    #  Cooldown System
    # ──────────────────────────────────────────

    def _can_alert(self, alert_type: str) -> bool:
        """
        Check if enough time has elapsed since the last alert of this type.
        If yes, records the current time and returns True.
        """
        now = time.time()
        last = self._cooldowns.get(alert_type, 0)
        cooldown = self._cooldown_durations.get(alert_type, 300)

        if (now - last) >= cooldown:
            self._cooldowns[alert_type] = now
            return True
        return False

    # ──────────────────────────────────────────
    #  Check Routines
    # ──────────────────────────────────────────

    def _run_checks(self) -> None:
        """Execute all monitoring checks in sequence."""
        self._check_battery()
        self._check_ram()
        self._check_cpu()
        self._check_break_reminder()
        self._check_late_night()
        self._check_time_based()

    def _check_battery(self) -> None:
        """Monitor battery level and charging state."""
        try:
            battery = psutil.sensors_battery()
            if battery is None:
                return  # no battery (desktop PC)

            pct = int(battery.percent)
            plugged = battery.power_plugged

            # Critical: ≤10% and not plugged
            if pct <= 10 and not plugged:
                self._queue_alert(
                    f"Critical warning Mayank, battery is at {pct} percent. "
                    "Please plug in immediately.",
                    "battery_critical",
                    "critical",
                )

            # Low: ≤20% and not plugged
            elif pct <= 20 and not plugged:
                self._queue_alert(
                    f"Mayank, battery is at {pct} percent. "
                    "You might want to plug in soon.",
                    "battery_low",
                    "warning",
                )

            # Full: 100% and plugged
            elif pct == 100 and plugged:
                self._queue_alert(
                    "Battery fully charged. You can unplug now, Mayank.",
                    "battery_full",
                    "info",
                )

        except Exception as e:
            logger.debug(f"Battery check error: {e}")

    def _check_ram(self) -> None:
        """Monitor RAM usage."""
        try:
            ram = psutil.virtual_memory()
            pct = ram.percent

            # Critical: ≥95%
            if pct >= 95:
                self._queue_alert(
                    f"Warning. System memory critical at {pct:.0f} percent. "
                    "Performance may be affected.",
                    "ram_critical",
                    "critical",
                )
            # High: ≥90%
            elif pct >= 90:
                self._queue_alert(
                    f"Mayank, RAM usage is at {pct:.0f} percent. "
                    "Consider closing some applications.",
                    "ram_high",
                    "warning",
                )

        except Exception as e:
            logger.debug(f"RAM check error: {e}")

    def _check_cpu(self) -> None:
        """
        Monitor CPU usage — alert only after 3 consecutive high readings.
        Uses a 5-second interval measurement for accuracy.
        """
        try:
            cpu = psutil.cpu_percent(interval=5)

            if cpu >= 85:
                self._cpu_high_streak += 1
            else:
                self._cpu_high_streak = 0

            # Only alert after 3 consecutive high readings (~3 check cycles)
            if self._cpu_high_streak >= 3:
                self._queue_alert(
                    f"CPU running hot at {cpu:.0f} percent. "
                    "Heavy process detected.",
                    "cpu_high",
                    "warning",
                )
                self._cpu_high_streak = 0  # reset after alerting

        except Exception as e:
            logger.debug(f"CPU check error: {e}")

    def _check_break_reminder(self) -> None:
        """Remind Mayank to take a break after 3 hours of continuous use."""
        elapsed_hours = (time.time() - self._last_break_reset) / 3600

        if elapsed_hours >= 3.0:
            hours_str = f"{elapsed_hours:.0f}"
            self._queue_alert(
                f"Mayank, you've been working for {hours_str} hours straight. "
                "Consider taking a short break.",
                "break_reminder",
                "info",
            )
            # Reset the timer after the reminder
            self._last_break_reset = time.time()

    def _check_late_night(self) -> None:
        """Alert if working between 1 AM and 4 AM."""
        hour = datetime.now().hour

        if 1 <= hour <= 4:
            time_str = datetime.now().strftime("%I:%M %p")
            self._queue_alert(
                f"It's {time_str} in the morning Mayank. "
                "Make sure to get some rest.",
                "midnight_alert",
                "info",
            )

    def _check_time_based(self) -> None:
        """
        Trigger time-based check-ins:
          9:00 AM  — morning briefing (if not already done)
          1:00 PM  — afternoon check-in
          6:00 PM  — evening weather update
        """
        now = datetime.now()
        hour = now.hour
        minute = now.minute

        # Use a 2-minute window to catch the event (checks run every 60s)
        # 9:00 AM — morning briefing trigger
        if hour == 9 and minute <= 1:
            if self._can_alert("morning_checkin"):
                try:
                    from core.briefing import MorningBriefing
                    briefing = MorningBriefing()
                    if briefing.should_greet():
                        text = briefing.generate_briefing()
                        self._speak_safe(text, "morning_checkin", "info")
                except Exception as e:
                    logger.warning(f"Morning check-in briefing failed: {e}")
                return  # don't re-enter _can_alert check below

        # 1:00 PM — afternoon check-in
        if hour == 13 and minute <= 1:
            self._queue_alert(
                "Afternoon check-in. Hope the work is going well, Mayank.",
                "afternoon_checkin",
                "info",
            )

        # 6:00 PM — evening weather update
        if hour == 18 and minute <= 1:
            weather_summary = self._get_evening_weather()
            self._queue_alert(
                f"Evening update. {weather_summary}",
                "evening_checkin",
                "info",
            )

    def _get_evening_weather(self) -> str:
        """Fetch a brief weather summary for the evening check-in."""
        try:
            from skills.world_briefing import _fetch_weather

            weather = _fetch_weather("Delhi")
            if weather and weather.get("condition") != "unavailable":
                temp = weather.get("temp", 0)
                condition = weather.get("condition", "")
                return f"Delhi is currently {temp} degrees, {condition}."
            return "Weather data is currently unavailable."
        except Exception as e:
            logger.debug(f"Evening weather fetch failed: {e}")
            return "Couldn't fetch the weather right now."

    # ──────────────────────────────────────────
    #  Safe Speaking & Queue System
    # ──────────────────────────────────────────

    def _queue_alert(self, message: str, alert_type: str, severity: str) -> None:
        """
        Check cooldown and queue the alert for speaking.
        Also broadcasts a WebSocket event immediately (UI doesn't need
        to wait for TTS availability).
        """
        if not self._can_alert(alert_type):
            return

        logger.info(f"Proactive alert queued: [{alert_type}] {message}")

        # Broadcast to UI immediately
        self.event_bus.broadcast("proactive_alert", {
            "type": alert_type,
            "message": message,
            "severity": severity,
        })

        # Queue for TTS
        with self._queue_lock:
            self._alert_queue.append((message, alert_type, severity))

    def _process_queue(self) -> None:
        """
        Try to speak queued alerts.  Respects:
          - tts.is_speaking — don't interrupt active speech
          - jarvis_state["in_conversation"] — delay during conversations
          - Max 1 spoken alert per 60 seconds
        """
        with self._queue_lock:
            if not self._alert_queue:
                return

        # Check if Jarvis is busy
        if self._is_jarvis_busy():
            logger.debug("Jarvis is busy — delaying proactive alerts.")
            return

        # Rate limit: max 1 spoken alert per 60 seconds
        now = time.time()
        if (now - self._last_alert_spoken) < 60:
            return

        # Pop the next alert
        with self._queue_lock:
            if not self._alert_queue:
                return
            message, alert_type, severity = self._alert_queue.pop(0)

        self._speak_safe(message, alert_type, severity)

    def _speak_safe(self, message: str, alert_type: str, severity: str) -> None:
        """
        Speak a message via TTS with safety checks.
        Blocks until TTS finishes, then records the timestamp.
        """
        # Final check: don't speak if Jarvis became busy between queue and now
        if self._is_jarvis_busy():
            # Re-queue for later
            with self._queue_lock:
                self._alert_queue.insert(0, (message, alert_type, severity))
            return

        try:
            print(f"\n🔔  [PROACTIVE] {message}")
            self.jarvis_state["is_speaking"] = True
            self.tts.speak(message)
            self.jarvis_state["is_speaking"] = False
            self._last_alert_spoken = time.time()
        except Exception as e:
            logger.error(f"Proactive TTS error: {e}")
            self.jarvis_state["is_speaking"] = False

    def _is_jarvis_busy(self) -> bool:
        """
        Check if Jarvis is currently busy (speaking, listening, or
        in an active conversation).
        """
        if self.tts.is_speaking:
            return True
        if self.jarvis_state.get("is_speaking", False):
            return True
        if self.jarvis_state.get("in_conversation", False):
            return True
        if self.jarvis_state.get("is_listening", False):
            return True
        return False
