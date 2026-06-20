"""
skills/app_launcher.py — Application Launcher Skill

Opens desktop applications on Windows by fuzzy-matching the app name
from the user's query against a known dictionary of app → executable
mappings.

Uses ``subprocess.Popen()`` to launch without blocking the assistant,
and ``difflib.get_close_matches()`` for fuzzy matching (no extra deps).
"""

import difflib
import os
import subprocess

from skills.base_skill import BaseSkill


# ──────────────────────────────────────────────
#  Known Applications → Executable Paths
# ──────────────────────────────────────────────

APP_MAP: dict[str, str] = {
    "chrome":          "chrome.exe",
    "google chrome":   "chrome.exe",
    "brave":           "brave.exe",
    "firefox":         "firefox.exe",
    "edge":            "msedge.exe",
    "vs code":         "code",
    "vscode":          "code",
    "visual studio code": "code",
    "spotify":         os.path.expandvars(
        r"%APPDATA%\Spotify\Spotify.exe"
    ),
    "notepad":         "notepad.exe",
    "file explorer":   "explorer.exe",
    "explorer":        "explorer.exe",
    "calculator":      "calc.exe",
    "calc":            "calc.exe",
    "task manager":    "taskmgr.exe",
    "terminal":        "wt.exe",
    "windows terminal": "wt.exe",
    "cmd":             "cmd.exe",
    "command prompt":  "cmd.exe",
    "powershell":      "powershell.exe",
    "word":            "winword.exe",
    "microsoft word":  "winword.exe",
    "excel":           "excel.exe",
    "microsoft excel": "excel.exe",
    "powerpoint":      "powerpnt.exe",
    "paint":           "mspaint.exe",
    "snipping tool":   "snippingtool.exe",
    "settings":        "ms-settings:",
    "control panel":   "control.exe",
}


class AppLauncherSkill(BaseSkill):
    """Opens desktop applications by fuzzy-matching the app name."""

    @property
    def name(self) -> str:
        return "App Launcher"

    @property
    def keywords(self) -> list[str]:
        return ["open", "launch", "start", "run"]

    def execute(self, query: str) -> str:
        """Parse app name from query and launch it."""
        import re

        q_lower = query.lower()

        # Detect if user wants to type/write after opening
        has_write_intent = bool(re.search(r'\band\s+(write|type)\b', q_lower))

        # Strip everything after " and " to isolate the app name
        clean_query = re.split(r'\s+and\s+', query, maxsplit=1)[0]

        app_name = self._extract_app_name(clean_query)
        if not app_name:
            return "Which application would you like me to open?"

        # Direct match first
        exe = APP_MAP.get(app_name)

        # Fuzzy match if no direct hit
        if exe is None:
            close = difflib.get_close_matches(
                app_name, APP_MAP.keys(), n=1, cutoff=0.5
            )
            if close:
                matched = close[0]
                exe = APP_MAP[matched]
                app_name = matched  # use the canonical name for response
            else:
                # LLM Fallback (Layer 2)
                try:
                    import yaml
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
                        "Return ONLY a single executable shell command. \n"
                        "No explanation. No markdown. Just the command."
                    )
                    user_prompt = f"Generate Windows shell command to: {query}"

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
                        cmd,
                        shell=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    return "Done, executing your request."
                except Exception as e:
                    print(f"Fallback execution error: {e}")
                    return "Sorry, I couldn't figure that out."

        result = self._launch(app_name, exe)

        if has_write_intent:
            result += " Note: I can open apps but can't type inside them yet."

        return result

    # ── Helpers ─────────────────────────────────

    @staticmethod
    def _extract_app_name(query: str) -> str:
        """
        Strip the trigger verb to isolate the app name.

        Examples:
            "open Google Chrome"   → "google chrome"
            "launch VS Code"      → "vs code"
            "start task manager"  → "task manager"
        """
        q = query.lower().strip()

        # Remove leading trigger words
        for prefix in ("open ", "launch ", "start ", "run ", "please "):
            if q.startswith(prefix):
                q = q[len(prefix):]

        # Strip trailing filler
        for suffix in (" please", " for me", " app", " application"):
            if q.endswith(suffix):
                q = q[: -len(suffix)]

        return q.strip()

    @staticmethod
    def _launch(app_name: str, exe_path: str) -> str:
        """
        Launch the executable via subprocess.Popen().

        Uses shell=True so Windows can resolve exe names via PATH and
        handle protocol URIs like ``ms-settings:``.
        """
        try:
            if exe_path.endswith(":"):
                # Protocol URI (e.g. ms-settings:)
                os.startfile(exe_path)
            else:
                subprocess.Popen(
                    exe_path,
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            return f"Opening {app_name}."

        except FileNotFoundError:
            return f"I couldn't find {app_name} on this system."
        except Exception as e:
            return f"Failed to open {app_name}. Error: {e}"
