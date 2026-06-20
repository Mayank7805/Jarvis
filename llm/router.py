"""
llm/router.py — LLM Routing Engine

Routes user queries based on intent and connectivity:
  • Skills         → Local skill engine (instant, no LLM)
  • Weather queries → OpenWeatherMap API (direct, no LLM)
  • News queries    → NewsAPI (direct, no LLM)
  • Agent          → Gemini function-calling (tools: apps, web, typing, etc.)
  • Online  → Gemini Flash (cloud, fast, accurate)
  • Offline → Ollama (local CPU fallback)
"""

from __future__ import annotations

import requests

from llm.ollama_client import OllamaClient
from llm.gemini_client import GeminiClient
from skills.weather import get_weather, get_weather_data, extract_city
from skills.news import get_news, get_news_data
from skills.skill_manager import SkillManager
from server.event_bus import event_bus

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.memory import JarvisMemory
    from core.agent_executor import AgentExecutor


# ──────────────────────────────────────────────
#  Weather Detection Keywords
# ──────────────────────────────────────────────

WEATHER_KEYWORDS: list[str] = [
    "weather", "temperature", "temp", "degree", "celsius",
    "forecast", "humid", "humidity",
]


# ──────────────────────────────────────────────
#  News Detection Keywords
# ──────────────────────────────────────────────

NEWS_KEYWORDS: list[str] = [
    "news", "headlines", "headline", "happening in the world",
    "what's going on", "current affairs", "current events",
    "latest updates", "breaking news", "top stories",
    "what's happening", "whats happening", "going on in the world",
]


# ──────────────────────────────────────────────
#  World Dashboard Keywords
# ──────────────────────────────────────────────

WORLD_DASHBOARD_KEYWORDS: list[str] = [
    "what's happening in the world", "what is happening in the world",
    "world news", "tell me the news", "show me news",
    "world update", "news briefing", "what's going on in the world",
    "show me the news", "world intelligence",
]

EXPAND_NEWS_KEYWORDS: dict[str, int] = {
    "first": 0, "1st": 0,
    "second": 1, "2nd": 1,
    "third": 2, "3rd": 2,
}

CLOSE_DASHBOARD_KEYWORDS: list[str] = [
    "close dashboard", "hide dashboard", "close the dashboard",
    "hide the dashboard", "exit dashboard",
]


# ──────────────────────────────────────────────
#  Connectivity Check
# ──────────────────────────────────────────────

def is_online() -> bool:
    """
    Quick internet connectivity check.

    Sends a lightweight request to Google with a 2-second timeout.
    Returns True if reachable, False otherwise.
    """
    try:
        requests.get("https://www.google.com", timeout=2)
        return True
    except Exception:
        return False


# ──────────────────────────────────────────────
#  LLMRouter
# ──────────────────────────────────────────────

class LLMRouter:
    """
    Routes user queries to the appropriate LLM backend.

    - Online  → Gemini (cloud, default — fast and accurate).
    - Offline → Ollama (local CPU fallback).

    Args:
        ollama_model:  Model tag for Ollama (e.g. "phi3.5").
        gemini_model:  Model name for Gemini (e.g. "gemini-2.5-flash").
        max_history:   Max conversation turns to retain before trimming.
        memory:        Optional JarvisMemory instance for long-term memory.
        agent:         Optional AgentExecutor for Gemini function-calling tools.
    """

    def __init__(
        self,
        ollama_model: str = "phi3.5",
        gemini_model: str = "gemini-2.5-flash",
        internet_keywords: list[str] | None = None,  # kept for backwards compat, ignored
        max_history: int = 10,
        memory: JarvisMemory | None = None,
        agent: AgentExecutor | None = None,
    ) -> None:
        self.max_history = max_history
        self._history: list[dict[str, str]] = []
        self._memory = memory
        self._agent = agent

        # Initialize the skills engine (runs before any LLM)
        print("⚡  Initializing Skills Engine...")
        self._skill_manager = SkillManager()

        # Pass memory to skills that support it
        if self._memory is not None:
            self._skill_manager.set_memory(self._memory)

        # Initialize both LLM backends
        print("🧠  Initializing Ollama (local) client...")
        self._ollama = OllamaClient(model=ollama_model)
        print(f"✅  Ollama ready — model: {ollama_model}")

        print("☁️   Initializing Gemini (cloud) client...")
        self._gemini = GeminiClient(model=gemini_model)
        print(f"✅  Gemini ready — model: {gemini_model}")

    # ── Public API ──────────────────────────

    def route(self, text: str) -> str:
        """
        Determine which LLM should handle the query.

        Returns ``"gemini"`` if the device is online, else ``"ollama"``.
        """
        return "gemini" if is_online() else "ollama"

    def ask(self, text: str, history: list[dict[str, str]] | None = None) -> str:
        """
        Route the user's text to the correct LLM and return the response.

        Args:
            text:    The user's transcribed speech.
            history: Optional external conversation history.

        Returns:
            The LLM's response string.
        """
        working_history = history if history is not None else self._history

        # ── Fetch memory context for this query ──
        memory_context = ""
        if self._memory is not None:
            try:
                memory_context = self._memory.get_context(text)
            except Exception as e:
                print(f"⚠️  Memory context retrieval failed: {e}")

        # ── Skills engine intercept (fastest — no network, no LLM) ──
        skill_result = self._skill_manager.route_to_skill(text)
        if skill_result is not None:
            # Save to long-term memory even for skill responses
            self._save_to_memory(text, skill_result)
            # Broadcast content_update for World Monitor (skill-type detection)
            self._broadcast_skill_content(text, skill_result)
            if history is not None:
                pass  # caller manages external history
            else:
                self._history.append({"role": "user", "content": text})
                self._history.append({"role": "assistant", "content": skill_result})
                self._trim_history()
            return skill_result

        # ── Weather skill intercept (skip LLM entirely) ──
        text_lower = text.lower()
        if any(kw in text_lower for kw in WEATHER_KEYWORDS):
            print("🌤️  Weather query detected — using OpenWeatherMap API...")
            city = extract_city(text)
            reply, weather_data = get_weather_data(city)
            self._save_to_memory(text, reply)
            # Broadcast structured weather data to World Monitor
            if weather_data:
                event_bus.broadcast("content_update", {"type": "weather", "payload": weather_data})
            # Record in history so the LLM has context if user follows up
            if history is not None:
                pass  # caller already appended user message & will append response
            else:
                self._history.append({"role": "user", "content": text})
                self._history.append({"role": "assistant", "content": reply})
                self._trim_history()
            return reply

        # ── World Dashboard intercept (opens full-screen dashboard) ──
        if any(kw in text_lower for kw in WORLD_DASHBOARD_KEYWORDS):
            print("🌍  World dashboard requested — opening intelligence center...")
            event_bus.broadcast("open_dashboard", {})
            from skills.world_briefing import get_spoken_summary
            reply = get_spoken_summary()
            self._save_to_memory(text, reply)
            if history is not None:
                pass
            else:
                self._history.append({"role": "user", "content": text})
                self._history.append({"role": "assistant", "content": reply})
                self._trim_history()
            return reply

        # ── Close dashboard command ──
        if any(kw in text_lower for kw in CLOSE_DASHBOARD_KEYWORDS):
            event_bus.broadcast("close_dashboard", {})
            reply = "Closing the dashboard."
            return reply

        # ── Expand news command ("tell me more about first/second/third news") ──
        if "tell me more" in text_lower and any(kw in text_lower for kw in EXPAND_NEWS_KEYWORDS):
            for keyword, index in EXPAND_NEWS_KEYWORDS.items():
                if keyword in text_lower:
                    event_bus.broadcast("expand_news", {"index": index})
                    reply = "Expanding that story for you."
                    return reply

        # ── News skill intercept (skip LLM entirely) ──
        if any(kw in text_lower for kw in NEWS_KEYWORDS):
            print("📰  News query detected — using NewsAPI...")
            reply, headlines = get_news_data(text)
            self._save_to_memory(text, reply)
            # Broadcast structured news data to World Monitor
            if headlines:
                event_bus.broadcast("content_update", {"type": "news", "payload": {"headlines": headlines}})
            if history is not None:
                pass  # caller manages external history
            else:
                self._history.append({"role": "user", "content": text})
                self._history.append({"role": "assistant", "content": reply})
                self._trim_history()
            return reply

        backend = self.route(text)

        # ── Agent executor intercept (Gemini function calling) ──
        if self._agent is not None and backend == "gemini":
            print("🤖  Trying AgentExecutor (Gemini function calling)...")
            try:
                agent_result = self._agent.execute(text)
                if agent_result is not None:
                    print("   [OK] Agent handled the request.")
                    self._save_to_memory(text, agent_result)
                    if history is None:
                        self._history.append({"role": "user", "content": text})
                        self._history.append({"role": "assistant", "content": agent_result})
                        self._trim_history()
                    return agent_result
                print("   [→] Agent passed — falling through to conversation LLM.")
            except Exception as e:
                print(f"⚠️  Agent error: {e} — falling through to LLM.")

        try:
            if backend == "gemini":
                print("🌐  Routing to Gemini (online)...")
                reply = self._gemini.chat(text, history=working_history, memory_context=memory_context)
            else:
                print("🏠  Routing to Ollama (offline fallback)...")
                reply = self._ollama.chat(text, history=working_history, memory_context=memory_context)
        except Exception as e:
            print(f"⚠️  {backend.title()} failed, trying fallback...")
            # If primary fails, try the other backend
            try:
                if backend == "gemini":
                    reply = self._ollama.chat(text, history=working_history, memory_context=memory_context)
                    print("↩️   Fell back to Ollama.")
                else:
                    reply = self._gemini.chat(text, history=working_history, memory_context=memory_context)
                    print("↩️   Fell back to Gemini.")
            except Exception as fallback_err:
                return f"I'm sorry, both LLM backends are unavailable. Error: {fallback_err}"

        # Save to long-term memory
        self._save_to_memory(text, reply)

        # Update conversation history
        if history is None:
            self._history.append({"role": "user", "content": text})
            self._history.append({"role": "assistant", "content": reply})
            self._trim_history()

        return reply

    def ask_stream(self, text: str, history: list[dict[str, str]] | None = None):
        """
        Stream the response sentence-by-sentence.

        Mirrors the routing logic of ``ask()`` but yields sentences as they
        arrive instead of returning the full response at once.

        For non-LLM paths (skills, weather, news, agent) the complete
        response is yielded as a single item. For LLM backends, the
        streaming variant is used and sentences are yielded incrementally.

        After the generator is fully consumed, the turn is saved to
        long-term memory and conversation history.

        Args:
            text:    The user's transcribed speech.
            history: Optional external conversation history.

        Yields:
            str — One sentence (or full response for instant paths).
        """
        working_history = history if history is not None else self._history

        # ── Fetch memory context ──
        memory_context = ""
        if self._memory is not None:
            try:
                memory_context = self._memory.get_context(text)
            except Exception as e:
                print(f"⚠️  Memory context retrieval failed: {e}")

        # ── Skills engine intercept ──
        skill_result = self._skill_manager.route_to_skill(text)
        if skill_result is not None:
            self._save_to_memory(text, skill_result)
            self._broadcast_skill_content(text, skill_result)
            if history is None:
                self._history.append({"role": "user", "content": text})
                self._history.append({"role": "assistant", "content": skill_result})
                self._trim_history()
            yield skill_result
            return

        # ── Weather skill intercept ──
        text_lower = text.lower()
        if any(kw in text_lower for kw in WEATHER_KEYWORDS):
            print("🌤️  Weather query detected — using OpenWeatherMap API...")
            city = extract_city(text)
            reply, weather_data = get_weather_data(city)
            self._save_to_memory(text, reply)
            if weather_data:
                event_bus.broadcast("content_update", {"type": "weather", "payload": weather_data})
            if history is None:
                self._history.append({"role": "user", "content": text})
                self._history.append({"role": "assistant", "content": reply})
                self._trim_history()
            yield reply
            return

        # ── World Dashboard intercept (streaming path) ──
        if any(kw in text_lower for kw in WORLD_DASHBOARD_KEYWORDS):
            print("🌍  World dashboard requested — opening intelligence center...")
            event_bus.broadcast("open_dashboard", {})
            from skills.world_briefing import get_spoken_summary
            reply = get_spoken_summary()
            self._save_to_memory(text, reply)
            if history is None:
                self._history.append({"role": "user", "content": text})
                self._history.append({"role": "assistant", "content": reply})
                self._trim_history()
            yield reply
            return

        # ── Close dashboard command (streaming path) ──
        if any(kw in text_lower for kw in CLOSE_DASHBOARD_KEYWORDS):
            event_bus.broadcast("close_dashboard", {})
            yield "Closing the dashboard."
            return

        # ── Expand news command (streaming path) ──
        if "tell me more" in text_lower and any(kw in text_lower for kw in EXPAND_NEWS_KEYWORDS):
            for keyword, index in EXPAND_NEWS_KEYWORDS.items():
                if keyword in text_lower:
                    event_bus.broadcast("expand_news", {"index": index})
                    yield "Expanding that story for you."
                    return

        # ── News skill intercept ──
        if any(kw in text_lower for kw in NEWS_KEYWORDS):
            print("📰  News query detected — using NewsAPI...")
            reply, headlines = get_news_data(text)
            self._save_to_memory(text, reply)
            if headlines:
                event_bus.broadcast("content_update", {"type": "news", "payload": {"headlines": headlines}})
            if history is None:
                self._history.append({"role": "user", "content": text})
                self._history.append({"role": "assistant", "content": reply})
                self._trim_history()
            yield reply
            return

        backend = self.route(text)

        # ── Agent executor intercept ──
        if self._agent is not None and backend == "gemini":
            print("🤖  Trying AgentExecutor (Gemini function calling)...")
            try:
                agent_result = self._agent.execute(text)
                if agent_result is not None:
                    print("   [OK] Agent handled the request.")
                    self._save_to_memory(text, agent_result)
                    if history is None:
                        self._history.append({"role": "user", "content": text})
                        self._history.append({"role": "assistant", "content": agent_result})
                        self._trim_history()
                    yield agent_result
                    return
                print("   [→] Agent passed — falling through to streaming LLM.")
            except Exception as e:
                print(f"⚠️  Agent error: {e} — falling through to LLM.")

        # ── Streaming LLM path ──
        full_parts: list[str] = []
        try:
            if backend == "gemini":
                print("🌐  Streaming from Gemini (online)...")
                stream = self._gemini.stream_chat(text, history=working_history, memory_context=memory_context)
            else:
                print("🏠  Streaming from Ollama (offline fallback)...")
                stream = self._ollama.stream_chat(text, history=working_history, memory_context=memory_context)

            for sentence in stream:
                full_parts.append(sentence)
                yield sentence

        except Exception as e:
            print(f"⚠️  {backend.title()} streaming failed, trying fallback...")
            try:
                if backend == "gemini":
                    reply = self._ollama.chat(text, history=working_history, memory_context=memory_context)
                    print("↩️   Fell back to Ollama (non-streaming).")
                else:
                    reply = self._gemini.chat(text, history=working_history, memory_context=memory_context)
                    print("↩️   Fell back to Gemini (non-streaming).")
                full_parts = [reply]
                yield reply
            except Exception as fallback_err:
                error_msg = f"I'm sorry, both LLM backends are unavailable. Error: {fallback_err}"
                full_parts = [error_msg]
                yield error_msg

        # ── Post-stream: save to memory and history ──
        full_response = " ".join(full_parts).strip()
        if full_response:
            self._save_to_memory(text, full_response)
            if history is None:
                self._history.append({"role": "user", "content": text})
                self._history.append({"role": "assistant", "content": full_response})
                self._trim_history()

    def reset_history(self) -> None:
        """Clear conversation history across all backends."""
        self._history.clear()
        self._ollama.reset_history()
        self._gemini.reset_history()

    @property
    def history(self) -> list[dict[str, str]]:
        """Return a copy of the current conversation history."""
        return list(self._history)

    # ── Internal helpers ────────────────────

    def _save_to_memory(self, user_text: str, assistant_reply: str) -> None:
        """Persist the user + assistant turn to long-term memory."""
        if self._memory is None:
            return
        try:
            self._memory.save("user", user_text)
            self._memory.save("assistant", assistant_reply)
        except Exception as e:
            print(f"⚠️  Failed to save to memory: {e}")

    def _trim_history(self) -> None:
        """Keep only the last ``max_history`` turns (each turn = 2 messages)."""
        max_messages = self.max_history * 2  # user + assistant per turn
        if len(self._history) > max_messages:
            self._history = self._history[-max_messages:]

    @staticmethod
    def _broadcast_skill_content(text: str, result: str) -> None:
        """
        Detect the skill type from the query/result and broadcast
        a content_update event for the World Monitor UI.
        """
        import psutil

        text_lower = text.lower()

        # Music skill
        if any(kw in text_lower for kw in ("play ", "stop music", "pause music", "resume music")):
            # Parse title/artist from result like "Playing X by Y."
            title, artist, status = "Unknown", "Unknown", "playing"
            if "playing" in result.lower():
                import re
                m = re.search(r"Playing (.+?) by (.+?)\.", result)
                if m:
                    title, artist = m.group(1), m.group(2)
                status = "playing"
            elif "paused" in result.lower():
                status = "paused"
            elif "stopped" in result.lower():
                status = "stopped"
            elif "resumed" in result.lower():
                status = "playing"
            event_bus.broadcast("content_update", {
                "type": "music",
                "payload": {"title": title, "artist": artist, "status": status},
            })
            return

        # System info skill
        if any(kw in text_lower for kw in ("battery", "ram", "memory", "cpu", "disk", "storage", "system info", "performance")):
            try:
                cpu = psutil.cpu_percent(interval=None)
                ram = psutil.virtual_memory().percent
                battery = psutil.sensors_battery()
                bat_pct = int(battery.percent) if battery else -1
                disk = psutil.disk_usage("C:\\").percent
                event_bus.broadcast("content_update", {
                    "type": "system",
                    "payload": {"cpu": cpu, "ram": ram, "battery": bat_pct, "disk": disk},
                })
            except Exception:
                pass
            return

        # Screenshot skill
        if any(kw in text_lower for kw in ("screenshot", "screen capture", "capture")):
            # Extract filename from result like "Screenshot saved to screenshot_20240101_120000.png."
            import re
            m = re.search(r"(screenshot_[\w]+\.png)", result, re.IGNORECASE)
            filepath = m.group(1) if m else ""
            event_bus.broadcast("content_update", {
                "type": "screenshot",
                "payload": {"filepath": filepath},
            })
            return

        # Timer skill — already handled inside timer.py via event_bus
        if any(kw in text_lower for kw in ("timer", "alarm", "remind me in")):
            return

        # Default: broadcast search/general for LLM-like responses from skills
        event_bus.broadcast("content_update", {
            "type": "search",
            "payload": {"query": text, "summary": result, "url": ""},
        })
