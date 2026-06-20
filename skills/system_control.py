"""
skills/system_control.py — System Control Skill

Controls volume, brightness, and system power state on Windows 11.

Dependencies:
    pip install pycaw comtypes screen-brightness-control

Handles:
    • Volume   → pycaw (Windows Core Audio API via COM)
    • Brightness → screen-brightness-control
    • Shutdown / Restart / Lock / Sleep → os.system() & ctypes
"""

import os
import re

from skills.base_skill import BaseSkill


class SystemControlSkill(BaseSkill):
    """Handles volume, brightness, and power control commands."""

    @property
    def name(self) -> str:
        return "System Control"

    @property
    def keywords(self) -> list[str]:
        return [
            "volume", "brightness", "shutdown", "restart",
            "lock", "sleep mode", "turn off",
        ]

    def execute(self, query: str) -> str:
        """Route to the appropriate system control function."""
        q = query.lower()

        if "volume" in q:
            level = self._extract_level(q)
            if level is not None:
                return self._set_volume(level)
            if "mute" in q:
                return self._set_volume(0)
            if "max" in q or "full" in q:
                return self._set_volume(100)
            return "Please tell me what level to set the volume to, like set volume to 50."

        if "brightness" in q:
            level = self._extract_level(q)
            if level is not None:
                return self._set_brightness(level)
            if "max" in q or "full" in q:
                return self._set_brightness(100)
            if "min" in q or "low" in q:
                return self._set_brightness(10)
            return "Please tell me what brightness level you want, like set brightness to 70."

        if "shutdown" in q or "turn off" in q:
            return self._shutdown()

        if "restart" in q:
            return self._restart()

        if "lock" in q:
            return self._lock_pc()

        if "sleep" in q:
            return self._sleep_pc()

        # LLM Fallback (Layer 2)
        try:
            import yaml
            import subprocess
            from google import genai
            from google.genai import types

            api_model = "gemini-2.5-flash"
            try:
                config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "jarvis.yaml")
                with open(config_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                    api_model = config.get("llm", {}).get("api_model", "gemini-2.5-flash")
            except Exception:
                pass

            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("GEMINI_API_KEY not found in environment.")

            client = genai.Client(api_key=api_key)
            system_prompt = (
                "You are a Windows 11 command expert. \n"
                "Return ONLY a single executable PowerShell command. \n"
                "No explanation. No markdown. Just the command."
            )
            user_prompt = f"Generate Windows PowerShell command to: {query}"

            response = client.models.generate_content(
                model=api_model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                )
            )
            cmd = response.text.strip()

            # Clean markdown code fences if any
            if cmd.startswith("```"):
                lines = cmd.splitlines()
                if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].startswith("```"):
                    cmd = "\n".join(lines[1:-1]).strip()
            cmd = cmd.strip('`').strip()

            cmd_lower = cmd.lower()
            if any(danger in cmd_lower for danger in ["del", "format", "rm"]):
                return "That seems risky, I won't do that."

            subprocess.Popen(
                ["powershell", "-Command", cmd],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return "Done, executing your request."
        except Exception as e:
            print(f"Fallback execution error: {e}")
            return "Sorry, I couldn't figure that out."

    # ── Volume (pycaw) ─────────────────────────

    @staticmethod
    def _set_volume(level: int) -> str:
        """
        Set system volume to *level* (0–100) using pycaw.

        pycaw uses Windows COM, so we initialise COM in this thread
        to avoid threading issues with the audio pipeline.
        """
        try:
            import comtypes
            comtypes.CoInitialize()

            from pycaw.pycaw import AudioUtilities

            device = AudioUtilities.GetSpeakers()
            volume = device.EndpointVolume

            # pycaw volume is in dB; use scalar (0.0 – 1.0)
            scalar = max(0.0, min(1.0, level / 100.0))
            volume.SetMasterVolumeLevelScalar(scalar, None)

            return f"Volume set to {level} percent."

        except Exception as e:
            return f"Sorry, I couldn't set the volume. Error: {e}"

    # ── Brightness (screen-brightness-control) ─

    @staticmethod
    def _set_brightness(level: int) -> str:
        """Set display brightness to *level* (0–100)."""
        try:
            import screen_brightness_control as sbc

            level = max(0, min(100, level))
            sbc.set_brightness(level)
            return f"Brightness set to {level} percent."

        except Exception as e:
            return f"Sorry, I couldn't set the brightness. Error: {e}"

    # ── Power controls ─────────────────────────

    @staticmethod
    def _shutdown() -> str:
        """Schedule a Windows shutdown in 5 seconds (gives time to cancel)."""
        os.system("shutdown /s /t 5")
        return "Shutting down in 5 seconds. Say shutdown abort to cancel."

    @staticmethod
    def _restart() -> str:
        """Schedule a Windows restart in 5 seconds."""
        os.system("shutdown /r /t 5")
        return "Restarting in 5 seconds."

    @staticmethod
    def _lock_pc() -> str:
        """Lock the workstation immediately."""
        import ctypes
        ctypes.windll.user32.LockWorkStation()
        return "Locking the PC now."

    @staticmethod
    def _sleep_pc() -> str:
        """Put the PC to sleep via rundll32."""
        os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
        return "Putting the PC to sleep."

    # ── Helpers ─────────────────────────────────

    @staticmethod
    def _extract_level(text: str) -> int | None:
        """
        Extract a numeric level from text.

        Examples:
            "set volume to 50"  → 50
            "brightness 75"     → 75
            "volume at 30%"     → 30
        """
        match = re.search(r"(\d+)\s*%?", text)
        if match:
            return int(match.group(1))
        return None
