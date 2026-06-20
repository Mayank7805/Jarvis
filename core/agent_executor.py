"""
core/agent_executor.py — Agentic Execution Engine

Uses Gemini function calling to intelligently decide which tool to invoke
for ANY user request. Instead of keyword matching, Gemini acts as Jarvis's
action planner — choosing the right tool and parameters.

Tools available:
    1. run_command     — Execute Windows shell commands
    2. open_url        — Open URL in default browser
    3. type_text       — Type text via keyboard simulation
    4. press_key       — Press keyboard shortcuts
    5. set_system      — Volume/brightness/power control
    6. search_and_open — Google search in browser
    7. get_system_info — Battery/CPU/RAM/disk info
    8. write_to_file   — Create/write files on Desktop
    9. take_action_with_code — Execute Gemini-generated Python (restricted)
"""

import os
import re
import subprocess
import webbrowser
from pathlib import Path

from google import genai
from google.genai import types


# ──────────────────────────────────────────────
#  Constants
# ──────────────────────────────────────────────

AGENT_SYSTEM_PROMPT = (
    "You are Jarvis's action planner running on Windows 11.\n"
    "Given a user request, choose the most appropriate tool to fulfill it.\n"
    "For opening apps: use run_command with Windows app commands.\n"
    "Common Windows commands:\n"
    "  - Camera: 'start microsoft.windows.camera:'\n"
    "  - Settings: 'start ms-settings:'\n"
    "  - Photos: 'start ms-photos:'\n"
    "  - Store: 'start ms-windows-store:'\n"
    "  - Paint: 'mspaint.exe'\n"
    "  - Snipping tool: 'snippingtool.exe'\n"
    "  - Chrome: 'start chrome'\n"
    "  - Brave: 'start brave'\n"
    "  - Firefox: 'start firefox'\n"
    "  - Edge: 'start msedge'\n"
    "  - VS Code: 'code'\n"
    "  - Notepad: 'notepad.exe'\n"
    "  - File Explorer: 'explorer.exe'\n"
    "  - Calculator: 'calc.exe'\n"
    "  - Task Manager: 'taskmgr.exe'\n"
    "  - Terminal: 'wt.exe'\n"
    "  - Word: 'start winword'\n"
    "  - Excel: 'start excel'\n"
    "  - PowerPoint: 'start powerpnt'\n"
    "  - Spotify: 'start spotify:'\n"
    "  - Any installed app: use its .exe name or 'start' + protocol URI\n"
    "  - Websites: use open_url tool\n"
    "If the request is purely conversational (greeting, question, opinion, "
    "general knowledge, advice, or small talk), do NOT call any tool — "
    "just respond with a short text answer.\n"
    "Always prefer the most specific tool for the job."
)

# Commands that are blocked for safety
_BLOCKED_COMMANDS = {
    "del ", "format ", "rm ", "rmdir ", "rd ",
    "del/", "remove-item", "clear-disk",
}

# Modules allowed inside take_action_with_code
_ALLOWED_MODULES = {
    "os", "subprocess", "pathlib", "datetime", "webbrowser",
    "pyautogui", "time", "math", "json", "re",
}

# Patterns forbidden in code execution
_FORBIDDEN_CODE_PATTERNS = [
    r"\bsocket\b", r"\brequests\b", r"\burllib\b",
    r"\b__import__\b", r"\beval\s*\(", r"\bexec\s*\(",
    r"\bcompile\s*\(", r"\bopen\s*\(.*/etc",
]


# ──────────────────────────────────────────────
#  Tool Functions (called by the agent)
# ──────────────────────────────────────────────

def _tool_run_command(command: str) -> str:
    """
    Run a Windows shell command.

    Args:
        command: The shell command to execute (e.g. 'start chrome', 'notepad.exe').

    Returns:
        A string describing the result.
    """
    cmd_lower = command.lower().strip()

    # Safety check
    if any(blocked in cmd_lower for blocked in _BLOCKED_COMMANDS):
        return "I've blocked that command for safety reasons."

    try:
        subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return f"Done, executing: {command}"
    except Exception as e:
        return f"Failed to run command. Error: {e}"


def _tool_open_url(url: str) -> str:
    """
    Open a URL in the default web browser.

    Args:
        url: The full URL to open (e.g. 'https://www.google.com').

    Returns:
        A string confirming the URL was opened.
    """
    # Ensure the URL has a scheme
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        webbrowser.open(url)
        return f"Opening {url} in your browser."
    except Exception as e:
        return f"Failed to open URL. Error: {e}"


def _tool_type_text(text: str) -> str:
    """
    Type text using keyboard simulation. The text will be typed at the current cursor position.

    Args:
        text: The text to type.

    Returns:
        A string confirming the text was typed.
    """
    try:
        import pyautogui
        import time

        # Small delay to let user focus the target window
        time.sleep(0.5)
        pyautogui.typewrite(text, interval=0.02)
        return f"Typed: {text}"
    except Exception as e:
        return f"Failed to type text. Error: {e}"


def _tool_press_key(key: str) -> str:
    """
    Press a keyboard shortcut or key combination.

    Args:
        key: Comma-separated key names (e.g. 'ctrl,c' for copy, 'alt,f4' to close window, 'enter').

    Returns:
        A string confirming the key press.
    """
    try:
        import pyautogui

        keys = [k.strip().lower() for k in key.split(",")]
        pyautogui.hotkey(*keys)
        return f"Pressed: {' + '.join(keys)}"
    except Exception as e:
        return f"Failed to press key. Error: {e}"


def _tool_set_system(action: str, value: str) -> str:
    """
    Control system settings like volume, brightness, or power state.

    Args:
        action: The system action — one of 'volume', 'brightness', 'shutdown', 'restart', 'lock', 'sleep'.
        value: The value to set (e.g. '50' for 50 percent, or 'mute', 'max'). Use 'now' for power actions.

    Returns:
        A string describing what was done.
    """
    from skills.system_control import SystemControlSkill

    skill = SystemControlSkill()

    # Build a synthetic query the skill can parse
    if action.lower() in ("shutdown", "restart", "lock", "sleep"):
        synthetic_query = action.lower()
    else:
        synthetic_query = f"set {action} to {value}"

    return skill.execute(synthetic_query)


def _tool_search_and_open(query: str) -> str:
    """
    Search Google for a query and open the results page in the default browser.

    Args:
        query: The search query (e.g. 'Python tutorials', 'best restaurants nearby').

    Returns:
        A string confirming the search was opened.
    """
    from urllib.parse import quote_plus

    search_url = f"https://www.google.com/search?q={quote_plus(query)}"
    try:
        webbrowser.open(search_url)
        return f"Searching Google for: {query}"
    except Exception as e:
        return f"Failed to search. Error: {e}"


def _tool_get_system_info(info_type: str) -> str:
    """
    Get system information like battery level, CPU usage, RAM usage, or disk space.

    Args:
        info_type: The type of info — one of 'battery', 'cpu', 'ram', 'disk', or 'all'.

    Returns:
        A string with the requested system information.
    """
    from skills.system_info import SystemInfoSkill

    skill = SystemInfoSkill()
    return skill.execute(info_type)


def _tool_write_to_file(filename: str, content: str) -> str:
    """
    Create or write a file on the user's Desktop.

    Args:
        filename: The name of the file (e.g. 'notes.txt', 'script.py'). Will be placed on Desktop.
        content: The text content to write to the file.

    Returns:
        A string confirming the file was created.
    """
    # Sanitize filename — remove path separators to prevent directory traversal
    safe_name = re.sub(r'[<>:"/\\|?*]', "_", filename)
    desktop = Path(os.path.expanduser("~/Desktop"))
    file_path = desktop / safe_name

    try:
        file_path.write_text(content, encoding="utf-8")
        return f"File saved to Desktop: {safe_name}"
    except Exception as e:
        return f"Failed to write file. Error: {e}"


def _tool_take_action_with_code(python_code: str) -> str:
    """
    Execute Python code to perform an advanced action. Only use when no other tool fits.
    Allowed modules: os, subprocess, pathlib, datetime, webbrowser, pyautogui, time, math, json, re.
    Forbidden: socket, requests, urllib, __import__, eval, exec, compile.

    Args:
        python_code: The Python code to execute safely.

    Returns:
        A string with the execution result or output.
    """
    # Safety: check for forbidden patterns
    for pattern in _FORBIDDEN_CODE_PATTERNS:
        if re.search(pattern, python_code):
            return f"Blocked: code contains a forbidden pattern ({pattern})."

    # Build restricted globals
    import time
    import math
    import json
    import datetime
    import pathlib
    import pyautogui

    restricted_globals = {
        "__builtins__": {
            "print": print, "len": len, "str": str, "int": int,
            "float": float, "bool": bool, "list": list, "dict": dict,
            "tuple": tuple, "range": range, "enumerate": enumerate,
            "zip": zip, "map": map, "filter": filter, "sorted": sorted,
            "min": min, "max": max, "abs": abs, "round": round,
            "isinstance": isinstance, "type": type, "True": True,
            "False": False, "None": None,
        },
        "os": os,
        "subprocess": subprocess,
        "pathlib": pathlib,
        "Path": pathlib.Path,
        "datetime": datetime,
        "webbrowser": webbrowser,
        "pyautogui": pyautogui,
        "time": time,
        "math": math,
        "json": json,
        "re": re,
    }

    # Capture output
    output_lines = []
    original_print = print

    def _capture_print(*args, **kwargs):
        output_lines.append(" ".join(str(a) for a in args))

    restricted_globals["__builtins__"]["print"] = _capture_print

    try:
        exec(python_code, restricted_globals)
        if output_lines:
            return "Output: " + "; ".join(output_lines)
        return "Code executed successfully."
    except Exception as e:
        return f"Code execution error: {e}"


# ──────────────────────────────────────────────
#  All tools as a list for Gemini
# ──────────────────────────────────────────────

_TOOL_FUNCTIONS = [
    _tool_run_command,
    _tool_open_url,
    _tool_type_text,
    _tool_press_key,
    _tool_set_system,
    _tool_search_and_open,
    _tool_get_system_info,
    _tool_write_to_file,
    _tool_take_action_with_code,
]

# Map function names to callables for dispatch
# Gemini may call tools by their bare name (without _tool_ prefix),
# so we register both forms for reliable dispatch.
_TOOL_MAP: dict[str, callable] = {}
for fn in _TOOL_FUNCTIONS:
    _TOOL_MAP[fn.__name__] = fn
    # Also register without the _tool_ prefix
    bare_name = fn.__name__.removeprefix("_tool_")
    _TOOL_MAP[bare_name] = fn


# ──────────────────────────────────────────────
#  AgentExecutor
# ──────────────────────────────────────────────

class AgentExecutor:
    """
    Gemini-powered agentic execution engine.

    Sends user queries to Gemini with a set of tool definitions.
    Gemini decides which tool to call and with what arguments.
    AgentExecutor executes the tool and returns the result.
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
    ) -> None:
        # Resolve model from config or default
        self._model = model or self._load_model_from_config()

        # Resolve API key
        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            raise EnvironmentError(
                "GEMINI_API_KEY not found. Set it in your .env file."
            )

        self._client = genai.Client(api_key=key)
        print(f"🤖  AgentExecutor ready — model: {self._model}")

    def execute(self, user_query: str) -> str | None:
        """
        Send the user query to Gemini with all tools defined.

        If Gemini decides to call a tool → execute it and return the result.
        If Gemini responds with plain text (conversational) → return None
        to let the router fall through to regular chat.

        Args:
            user_query: The user's transcribed speech text.

        Returns:
            Tool execution result string, or None if no tool was called.
        """
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=user_query,
                config=types.GenerateContentConfig(
                    system_instruction=AGENT_SYSTEM_PROMPT,
                    tools=_TOOL_FUNCTIONS,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(
                        disable=True,
                    ),
                ),
            )
        except Exception as e:
            print(f"⚠️  Agent execution error: {e}")
            return None  # Fall through to regular LLM

        # Check if Gemini requested a function call
        if not response.function_calls:
            # No tool invoked — this is conversational, fall through
            return None

        # Execute the first function call
        fc = response.function_calls[0]
        tool_name = fc.name
        tool_args = dict(fc.args) if fc.args else {}

        print(f"🔧  Agent tool: {tool_name}({tool_args})")

        # Look up and execute the tool
        tool_fn = _TOOL_MAP.get(tool_name)
        if tool_fn is None:
            print(f"⚠️  Unknown tool: {tool_name}")
            return None

        try:
            result = tool_fn(**tool_args)
            return result
        except Exception as e:
            print(f"⚠️  Tool execution failed: {e}")
            return f"I tried to {tool_name} but encountered an error: {e}"

    # ── Internal helpers ────────────────────

    @staticmethod
    def _load_model_from_config() -> str:
        """Load the Gemini model name from jarvis.yaml, or use default."""
        try:
            import yaml

            config_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "config", "jarvis.yaml",
            )
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            return config.get("llm", {}).get("api_model", "gemini-2.5-flash")
        except Exception:
            return "gemini-2.5-flash"
