"""
core/briefing.py — Morning Briefing System

Generates a natural, conversational greeting spoken by Jarvis at startup.
Collects weather, date/day, system status, and a motivational close,
then passes the raw data through Gemini to produce flowing speech.

Tracks the last greeting timestamp in data/last_greeting.json to prevent
duplicate greetings within 30 minutes.
"""

import json
import random
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path

import psutil

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
#  Motivational Closing Lines (rotated randomly)
# ──────────────────────────────────────────────

MOTIVATIONAL_CLOSES: list[str] = [
    "What shall we work on today?",
    "Ready when you are, sir.",
    "Systems are online. What's the mission today?",
    "All systems nominal. How can I assist?",
    "At your service, Mayank.",
    "Standing by for your command.",
    "Let's make today count.",
    "Awaiting your instructions.",
    "The stage is set. What's the plan?",
    "All engines running. Lead the way.",
]

# Path to greeting timestamp tracker
_GREETING_FILE = Path("data") / "last_greeting.json"


class MorningBriefing:
    """
    Generates and manages Jarvis's startup greeting.

    Usage:
        briefing = MorningBriefing()
        if briefing.should_greet():
            text = briefing.generate_briefing()
            tts.speak(text)
    """

    # ──────────────────────────────────────────
    #  Greeting Gate
    # ──────────────────────────────────────────

    def should_greet(self) -> bool:
        """
        Check if Jarvis should deliver a greeting this session.

        Returns True only if the last greeting was more than 30 minutes
        ago (or if no greeting has ever been recorded).  When True,
        the current timestamp is saved to prevent re-greeting.
        """
        now = datetime.now()

        try:
            if _GREETING_FILE.exists():
                with open(_GREETING_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                last_str = data.get("last_greeted", "")
                if last_str:
                    last_time = datetime.fromisoformat(last_str)
                    if (now - last_time) < timedelta(minutes=30):
                        logger.info("Greeting skipped — last greeting was recent.")
                        return False
        except Exception as e:
            logger.warning(f"Could not read greeting file: {e}")

        # Save the current timestamp
        self._save_greeting_time(now)
        return True

    # ──────────────────────────────────────────
    #  Briefing Generation
    # ──────────────────────────────────────────

    def generate_briefing(self) -> str:
        """
        Generate a full morning briefing string.

        Collects five data points:
          1. Time-based greeting
          2. Weather for Delhi
          3. Date and day context
          4. System status (battery, RAM, CPU)
          5. Motivational closing line

        The raw paragraph is passed through Gemini for natural phrasing.
        Falls back to the raw paragraph if Gemini is unreachable.
        """
        parts: list[str] = []

        # 1. Time-based greeting
        parts.append(self._get_greeting())

        # 2. Weather
        weather_text = self._get_weather()
        if weather_text:
            parts.append(weather_text)

        # 3. Date and day
        parts.append(self._get_date_context())

        # 4. System status
        system_text = self._get_system_status()
        if system_text:
            parts.append(system_text)

        # 5. Motivational close
        parts.append(random.choice(MOTIVATIONAL_CLOSES))

        raw_briefing = " ".join(parts)

        # Polish with Gemini for natural, conversational speech
        polished = self._polish_with_gemini(raw_briefing)
        return polished

    # ──────────────────────────────────────────
    #  Data Collectors
    # ──────────────────────────────────────────

    def _get_greeting(self) -> str:
        """Return a time-appropriate greeting."""
        hour = datetime.now().hour

        if 5 <= hour < 11:
            return "Good morning Mayank."
        elif 11 <= hour < 17:
            return "Good afternoon Mayank."
        elif 17 <= hour < 21:
            return "Good evening Mayank."
        else:
            return "Working late again, Mayank."

    def _get_weather(self) -> str:
        """
        Fetch current weather for Delhi using the existing world_briefing
        weather function.  Returns a voice-friendly summary or empty string
        on failure.
        """
        try:
            from skills.world_briefing import _fetch_weather

            weather = _fetch_weather("Delhi")
            if weather and weather.get("condition") != "unavailable":
                temp = weather.get("temp", 0)
                condition = weather.get("condition", "")
                return f"Delhi is currently {temp} degrees Celsius, {condition}."
            return ""
        except Exception as e:
            logger.warning(f"Weather fetch failed for briefing: {e}")
            return ""

    def _get_date_context(self) -> str:
        """Return today's date with contextual remarks for special days."""
        now = datetime.now()
        day_name = now.strftime("%A")
        date_str = now.strftime("%B %d, %Y")

        base = f"Today is {day_name}, {date_str}."

        # Add day-specific flavour
        weekday = now.weekday()  # 0=Monday, 6=Sunday
        if weekday == 0:
            base += " New week, fresh start."
        elif weekday == 4:
            base += " It's Friday, weekend is close."
        elif weekday >= 5:
            base += " It's the weekend."

        return base

    def _get_system_status(self) -> str:
        """
        Check battery, RAM, and CPU via psutil.
        Only mentions metrics that are concerning.
        """
        alerts: list[str] = []

        try:
            # Battery check
            battery = psutil.sensors_battery()
            if battery and not battery.power_plugged and battery.percent < 30:
                alerts.append(
                    f"Your battery is at {int(battery.percent)} percent, "
                    "please plug in your charger."
                )

            # RAM check
            ram = psutil.virtual_memory()
            if ram.percent > 85:
                alerts.append(
                    f"System memory is running high at {ram.percent:.0f} percent."
                )

            # CPU check (non-blocking, uses last cached sample)
            cpu = psutil.cpu_percent(interval=None)
            if cpu > 80:
                alerts.append(f"CPU is currently at {cpu:.0f} percent.")

        except Exception as e:
            logger.warning(f"System status check failed: {e}")

        return " ".join(alerts) if alerts else ""

    # ──────────────────────────────────────────
    #  Gemini Polish
    # ──────────────────────────────────────────

    def _polish_with_gemini(self, raw_text: str) -> str:
        """
        Pass the raw briefing through Gemini to make it sound natural
        and conversational — like a real AI assistant greeting its user.

        Falls back to the raw text if Gemini is unavailable.
        """
        try:
            from llm.gemini_client import GeminiClient

            client = GeminiClient()
            prompt = (
                "You are Jarvis, a sophisticated AI assistant speaking to Mayank. "
                "Rephrase the following briefing data into ONE natural, flowing, "
                "conversational paragraph. Keep it concise — under 6 sentences. "
                "Do NOT add any information that isn't in the data. "
                "Do NOT use bullet points or lists. Speak in first person as Jarvis. "
                "Keep the greeting at the start and the motivational close at the end.\n\n"
                f"Raw data:\n{raw_text}"
            )
            polished = client.chat(prompt, history=[])
            if polished and len(polished.strip()) > 20:
                return polished.strip()
        except Exception as e:
            logger.warning(f"Gemini polish failed, using raw briefing: {e}")

        return raw_text

    # ──────────────────────────────────────────
    #  Helpers
    # ──────────────────────────────────────────

    def _save_greeting_time(self, timestamp: datetime) -> None:
        """Persist the greeting timestamp to data/last_greeting.json."""
        try:
            _GREETING_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(_GREETING_FILE, "w", encoding="utf-8") as f:
                json.dump({"last_greeted": timestamp.isoformat()}, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save greeting timestamp: {e}")
