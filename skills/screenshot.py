"""
skills/screenshot.py — Screenshot & Screen Reading Skill

Captures the screen using ``mss`` and optionally sends the image to
Gemini Vision (gemini-2.0-flash) for AI-powered screen reading.

Dependencies:
    pip install mss Pillow

Screenshots are saved to ``data/screenshots/`` with ISO-timestamp names.
"""

import io
import os
from datetime import datetime
from pathlib import Path

import mss
from PIL import Image
from google import genai
from google.genai import types

from skills.base_skill import BaseSkill


# Default screenshots directory
SCREENSHOTS_DIR = Path("data") / "screenshots"


class ScreenshotSkill(BaseSkill):
    """Takes screenshots and can describe screen contents via Gemini Vision."""

    def __init__(self, screenshots_dir: str | Path | None = None) -> None:
        self._screenshots_dir = Path(screenshots_dir) if screenshots_dir else SCREENSHOTS_DIR
        self._screenshots_dir.mkdir(parents=True, exist_ok=True)

    @property
    def name(self) -> str:
        return "Screenshot"

    @property
    def keywords(self) -> list[str]:
        return [
            "screenshot", "screen", "read screen",
            "what's on screen", "capture",
        ]

    def execute(self, query: str) -> str:
        """Take a screenshot and optionally read the screen content."""
        q = query.lower()

        # Determine if user wants screen *reading* (AI) or just a capture
        wants_read = any(
            phrase in q
            for phrase in ("read screen", "what's on screen", "what is on screen",
                           "describe screen", "analyze screen", "look at screen")
        )

        screenshot_path = self._take_screenshot()
        if screenshot_path is None:
            return "Sorry, I couldn't take a screenshot."

        if wants_read:
            return self._read_screen(screenshot_path, query)

        return f"Screenshot saved to {screenshot_path.name}."

    # ── Screenshot Capture ─────────────────────

    def _take_screenshot(self) -> Path | None:
        """
        Capture the primary monitor using mss and save as PNG.

        Returns the path to the saved file, or None on failure.
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
            filepath = self._screenshots_dir / filename

            with mss.mss() as sct:
                # Grab the primary monitor (index 1; 0 is all monitors combined)
                monitor = sct.monitors[1]
                raw = sct.grab(monitor)

                # mss provides .rgb for direct RGB byte data
                img = Image.frombytes("RGB", raw.size, raw.rgb)
                img.save(str(filepath), "PNG")

            print(f"[Screenshot] Saved: {filepath}")
            return filepath

        except Exception as e:
            print(f"[Screenshot] Failed: {e}")
            return None

    # ── Gemini Vision Screen Reader ────────────

    @staticmethod
    def _read_screen(image_path: Path, query: str) -> str:
        """
        Send the screenshot to Gemini Vision and return the description.

        Uses the same ``google.genai`` SDK already in the project.
        """
        try:

            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                return "I can't read the screen right now. The Gemini API key is missing."

            client = genai.Client(api_key=api_key)

            # Load the image
            img = Image.open(image_path)

            # Build the prompt
            # Strip trigger phrases to get the user's actual question
            clean_query = query
            for phrase in ("read screen", "read my screen", "what's on screen",
                           "what is on screen", "describe screen", "look at screen",
                           "analyze screen", "capture and"):
                clean_query = clean_query.lower().replace(phrase, "").strip()

            if not clean_query or len(clean_query) < 3:
                prompt = "Describe what you see on this screen. Be concise and voice-friendly."
            else:
                prompt = f"Look at this screen and {clean_query}. Be concise and voice-friendly."

            # Convert image to bytes for the API
            img_bytes = io.BytesIO()
            img.save(img_bytes, format="PNG")
            img_bytes.seek(0)

            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_bytes(
                                data=img_bytes.read(),
                                mime_type="image/png",
                            ),
                            types.Part.from_text(text=prompt),
                        ],
                    )
                ],
            )

            reply = response.text.strip()
            if not reply:
                return "I took a screenshot but couldn't describe what's on screen."
            return reply

        except Exception as e:
            return f"I took a screenshot but couldn't read the screen. Error: {e}"
