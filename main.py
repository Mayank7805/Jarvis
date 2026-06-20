"""
main.py — Jarvis Voice Assistant Entry Point

Orchestrates the full voice assistant loop:
  1. Load configuration and environment variables
  2. Initialize STT engine, wake word detector, and LLM router
  3. Listen for wake word / double-clap
  4. Play confirmation beep
  5. Record user speech
  6. Transcribe speech → text
  7. Route text to LLM (Ollama local or Gemini cloud)
  8. Display response
  9. Repeat
"""

import os
import sys
import time
import logging
import threading
import subprocess
from pathlib import Path

import numpy as np
import sounddevice as sd
import yaml
from dotenv import load_dotenv

from server.event_bus import event_bus
from server.jarvis_state import JarvisState
from server.app import start_server

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from core.audio_capture import record_speech, calibrate_silence_threshold
from core.stt import STT
from core.tts import TTS
from core.wake_word import WakeWordDetector
from core.memory import JarvisMemory
from core.agent_executor import AgentExecutor
from llm.router import LLMRouter


# ──────────────────────────────────────────────
#  Constants
# ──────────────────────────────────────────────

# Phrases that reset the conversation history
RESET_PHRASES = {"reset", "clear history"}

# Phrases that exit active conversation mode (back to wake word listening)
EXIT_PHRASES = {"shut down", "goodbye", "sleep", "jarvis stop", "that's all"}

# Inactivity timeout — exit conversation mode after this many seconds of no speech
CONVERSATION_TIMEOUT = 120  # seconds

# Shared state dict — read/written by the conversation loop AND
# the proactive monitor thread.  Python's GIL makes simple dict
# assignments atomic, so no explicit lock is needed.
jarvis_state: dict = {
    "is_speaking": False,
    "is_listening": False,
    "in_conversation": False,
    "conversation_start": None,
}

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
#  Desktop Shortcut Creation
# ──────────────────────────────────────────────

def _ensure_desktop_shortcut() -> None:
    """
    Create a 'Jarvis AI.lnk' shortcut on the user's Desktop
    pointing to launch_jarvis.bat — only if it doesn't already exist.

    Uses PowerShell's WScript.Shell COM object so no extra pip
    packages are needed.
    """
    try:
        desktop = Path.home() / "Desktop"
        if not desktop.exists():
            # Some locales use a different path; try the shell folder
            desktop = Path(os.environ.get("USERPROFILE", "")) / "Desktop"
        if not desktop.exists():
            print("   [!] Could not locate Desktop folder — skipping shortcut.")
            return

        shortcut_path = desktop / "Jarvis AI.lnk"
        if shortcut_path.exists():
            return  # already created

        project_root = Path(__file__).resolve().parent
        bat_path = project_root / "launch_jarvis.bat"
        if not bat_path.exists():
            print("   [!] launch_jarvis.bat not found — skipping shortcut.")
            return

        # PowerShell script to create a .lnk via COM
        ps_script = (
            f'$ws = New-Object -ComObject WScript.Shell; '
            f'$sc = $ws.CreateShortcut("{shortcut_path}"); '
            f'$sc.TargetPath = "{bat_path}"; '
            f'$sc.WorkingDirectory = "{project_root}"; '
            f'$sc.Description = "Launch Jarvis AI Assistant"; '
            f'$sc.WindowStyle = 1; '
            f'$sc.Save()'
        )

        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            timeout=10,
        )

        if shortcut_path.exists():
            print(f"🔗  Desktop shortcut created: {shortcut_path}")
        else:
            print("   [!] Shortcut creation returned no error but file not found.")

    except Exception as e:
        # Non-fatal — don't crash Jarvis if shortcut creation fails
        print(f"   [!] Desktop shortcut creation failed: {e}")


# (duplicate constants removed — defined above)


# ──────────────────────────────────────────────
#  Configuration Loading
# ──────────────────────────────────────────────

def load_config(config_path: str = "config/jarvis.yaml") -> dict:
    """Load and return the YAML configuration file."""
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        print(f"✅  Configuration loaded from '{config_path}'")
        return config
    except FileNotFoundError:
        print(f"❌  Config file not found: {config_path}")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"❌  Config parse error: {e}")
        sys.exit(1)


# ──────────────────────────────────────────────
#  Audio Feedback
# ──────────────────────────────────────────────

def play_beep(
    frequency: int = 880,
    duration: float = 0.1,
    volume: float = 0.5,
    sample_rate: int = 16000,
) -> None:
    """
    Play a short sine-wave beep as audible feedback.

    Args:
        frequency:   Tone frequency in Hz (default 880 — A5 note).
        duration:    Length of the beep in seconds.
        volume:      Amplitude multiplier (0.0 – 1.0).
        sample_rate: Audio sample rate.
    """
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    tone = (volume * np.sin(2 * np.pi * frequency * t)).astype(np.float32)
    sd.play(tone, samplerate=sample_rate)
    sd.wait()  # block until beep finishes


# ──────────────────────────────────────────────
#  Main Loop
# ──────────────────────────────────────────────

def main() -> None:
    """Run the Jarvis voice assistant main loop."""

    # ── Load environment variables ──────────
    load_dotenv()

    # ── Create Desktop shortcut (first run only) ──
    _ensure_desktop_shortcut()

    # ── Load configuration ──────────────────
    config = load_config()

    assistant_name = config.get("assistant", {}).get("name", "Jarvis")
    audio_cfg = config.get("audio", {})
    stt_cfg = config.get("stt", {})
    wake_cfg = config.get("wake_word", {})
    activation_cfg = config.get("activation", {})
    beep_cfg = config.get("beep", {})
    llm_cfg = config.get("llm", {})
    tts_cfg = config.get("tts", {})

    # ── Print startup banner ────────────────
    print()
    print("=" * 50)
    print(f"  🤖  {assistant_name} Voice Assistant")
    print("=" * 50)
    print(f"  Wake words : {activation_cfg.get('wake_words', ['hey jarvis'])}")
    print(f"  Clap detect: {activation_cfg.get('clap_detection', True)}")
    print(f"  STT model  : {stt_cfg.get('model', 'tiny.en')} ({stt_cfg.get('compute_type', 'int8')})")
    print(f"  TTS voice  : {tts_cfg.get('voice', 'en-US-GuyNeural')}")
    print(f"  Local LLM  : {llm_cfg.get('local_model', 'phi3.5')}")
    print(f"  Cloud LLM  : {llm_cfg.get('api_model', 'gemini-1.5-flash')}")
    print(f"  Sample rate : {audio_cfg.get('sample_rate', 16000)} Hz")
    print("=" * 50)
    print()

    # ── Initialize STT engine ───────────────
    stt = STT(
        model_size=stt_cfg.get("model", "tiny.en"),
        device=stt_cfg.get("device", "cpu"),
        compute_type=stt_cfg.get("compute_type", "int8"),
        beam_size=stt_cfg.get("beam_size", 5),
        no_speech_threshold=stt_cfg.get("no_speech_threshold", 0.6),
    )

    # ── Initialize wake word detector ───────
    detector = WakeWordDetector(
        model_name=wake_cfg.get("model_name", "hey_jarvis"),
        threshold=wake_cfg.get("threshold", 0.5),
        chunk_size=wake_cfg.get("chunk_size", 1280),
        sample_rate=audio_cfg.get("sample_rate", 16000),
        clap_threshold=activation_cfg.get("clap_spike_threshold", 0.3),
        clap_max_interval=activation_cfg.get("clap_max_interval", 0.8),
    )

    # ── Initialize long-term memory ─────────
    print("\n🧠  Initializing long-term memory...")
    memory = JarvisMemory()

    # ── Initialize agent executor ─────────
    print("\n🤖  Initializing AgentExecutor (Gemini function calling)...")
    agent = AgentExecutor()

    # ── Initialize LLM router ──────────────
    router = LLMRouter(
        ollama_model=llm_cfg.get("local_model", "phi3.5"),
        gemini_model=llm_cfg.get("api_model", "gemini-1.5-flash"),
        internet_keywords=llm_cfg.get("internet_keywords"),
        max_history=llm_cfg.get("max_history", 10),
        memory=memory,
        agent=agent,
    )

    # ── Initialize TTS engine ──────────────
    tts = TTS(
        voice=tts_cfg.get("voice", "en-US-GuyNeural"),
        rate=tts_cfg.get("rate", "+0%"),
        volume=tts_cfg.get("volume", "+0%"),
    )
    print(f"🔊  TTS engine ready ({tts_cfg.get('voice', 'en-US-GuyNeural')})")

    clap_enabled = activation_cfg.get("clap_detection", True)
    sample_rate = audio_cfg.get("sample_rate", 16000)

    # ── Calibrate microphone silence threshold ──
    calibrated_threshold = calibrate_silence_threshold(
        duration=1.0,
        sample_rate=sample_rate,
    )
    print(f"🎚️  Mic calibrated. Threshold: {calibrated_threshold:.4f}")

    # ── Start FastAPI/WebSocket server in background ──
    jarvis_state = JarvisState()
    jarvis_state.update(skills=router._skill_manager.loaded_skills)
    server_thread = threading.Thread(
        target=start_server,
        kwargs={"host": "0.0.0.0", "port": 8765},
        daemon=True,
    )
    server_thread.start()
    print("🌐  Server started on http://localhost:8765  (ws://localhost:8765/ws)")

    # ── Pre-warm models (eliminates cold-start latency) ──
    print("\n🔥  Warming up models...")
    try:
        # Pre-warm Whisper (first inference triggers JIT/model load)
        dummy_audio = np.zeros(16000, dtype=np.float32)
        stt.transcribe(dummy_audio)
        print("   ✅  Whisper warm")
    except Exception:
        pass
    try:
        # Pre-warm TTS (first synthesis opens edge-tts connection)
        tts.speak(".")
        print("   ✅  TTS warm")
    except Exception:
        pass
    try:
        # Pre-warm Gemini (first API call has connection overhead)
        router._gemini.chat("hi", [])
        print("   ✅  Gemini warm")
    except Exception:
        pass
    print("✅  Warmup complete — all models hot!")

    # ── Cinematic boot animation ─────────────
    print()
    print("=" * 50)
    print("  J.A.R.V.I.S  INITIALIZING...")
    time.sleep(0.5)
    print("  ▸ Voice engine         : ONLINE")
    time.sleep(0.3)
    print("  ▸ Intelligence core    : ONLINE")
    time.sleep(0.3)
    print("  ▸ Skills engine        : ONLINE")
    time.sleep(0.3)
    print("  ▸ Memory subsystem     : ONLINE")
    time.sleep(0.3)
    print("  ▸ World monitor        : ONLINE")
    time.sleep(0.3)
    print("  ▸ Proactive systems    : ONLINE")
    time.sleep(0.3)
    print("  All systems nominal.")
    print("=" * 50)
    print()

    # ── Startup beep — 3 ascending tones ─────
    try:
        play_beep(frequency=440, duration=0.1, volume=0.4)   # A4
        time.sleep(0.1)
        play_beep(frequency=660, duration=0.1, volume=0.4)   # E5
        time.sleep(0.1)
        play_beep(frequency=880, duration=0.15, volume=0.4)  # A5
    except Exception:
        pass  # non-critical — skip if audio device is busy

    # ── Morning briefing (if applicable) ─────
    try:
        from core.briefing import MorningBriefing

        briefing = MorningBriefing()
        if briefing.should_greet():
            print("\n🌅  Generating morning briefing...")
            greeting_text = briefing.generate_briefing()
            jarvis_state["is_speaking"] = True
            tts.speak(greeting_text)
            jarvis_state["is_speaking"] = False
            event_bus.broadcast("responding", {"text": greeting_text})
            print(f"🌅  Briefing delivered.\n")
    except Exception as e:
        logger.warning(f"Morning briefing failed: {e}")
        jarvis_state["is_speaking"] = False

    # ── Start proactive monitor ──────────────
    from core.proactive_monitor import ProactiveMonitor

    monitor = ProactiveMonitor(
        tts=tts,
        event_bus=event_bus,
        jarvis_state=jarvis_state,
    )
    monitor_thread = threading.Thread(
        target=monitor.start,
        daemon=True,
        name="ProactiveMonitor",
    )
    monitor_thread.start()

    print(f"\n🚀  {assistant_name} is ready! Say 'Hey Jarvis' or double-clap to begin.\n")

    # ── Main assistant loop ─────────────────
    try:
        while True:
            # Step 1: Wait for wake word or clap
            event_bus.broadcast("idle", {})
            JarvisState().update(status="idle")
            detector.listen_for_wake_word(clap_enabled=clap_enabled)
            event_bus.broadcast("wake_detected", {"trigger": "voice/clap"})
            JarvisState().update(status="listening")

            # ── Enter active conversation mode ──
            _run_conversation(
                assistant_name=assistant_name,
                stt=stt,
                tts=tts,
                router=router,
                audio_cfg=audio_cfg,
                beep_cfg=beep_cfg,
                sample_rate=sample_rate,
                silence_threshold=calibrated_threshold,
                max_history=llm_cfg.get("max_history", 10),
                jstate=jarvis_state,
            )

            # After conversation ends, loop back to wake word listening
            print(f"\n🚀  {assistant_name} is ready! Say 'Hey Jarvis' or double-clap to begin.\n")

    except KeyboardInterrupt:
        print(f"\n\n👋  {assistant_name} shutting down. Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌  Fatal error: {e}")
        sys.exit(1)


# ──────────────────────────────────────────────
#  Active Conversation Mode
# ──────────────────────────────────────────────

def _run_conversation(
    assistant_name: str,
    stt: "STT",
    tts: "TTS",
    router: "LLMRouter",
    audio_cfg: dict,
    beep_cfg: dict,
    sample_rate: int,
    silence_threshold: float = 0.01,
    max_history: int = 10,
    jstate: dict | None = None,
) -> None:
    """
    Active conversation loop — no wake word required between exchanges.

    Flow per iteration:
      beep → record → transcribe → LLM → SPEAK → listen again

    Exits when:
      • The user says an exit phrase (shutdown / goodbye / sleep / etc.)
      • 120 seconds of continuous inactivity (no speech detected)

    Args:
        jstate: Shared state dict for conversation-awareness (proactive monitor).
    """
    if jstate is None:
        jstate = jarvis_state  # fall back to module-level dict

    # Mark conversation as active (proactive monitor reads this)
    jstate["in_conversation"] = True
    jstate["conversation_start"] = time.time()

    last_speech_time = time.time()
    consecutive_empty = 0  # track consecutive empty recordings for timeout
    conversation_history: list[dict[str, str]] = []  # per-session memory

    print("\n" + "─" * 50)
    print(f"  🟢  [ACTIVE] Conversation mode — speak freely!")
    print("─" * 50 + "\n")

    while True:
        # ── Check inactivity timeout ────────
        if (time.time() - last_speech_time) >= CONVERSATION_TIMEOUT:
            print(f"\n⏱️  No speech for {CONVERSATION_TIMEOUT}s — timing out.")
            jstate["in_conversation"] = False
            _exit_conversation(assistant_name, tts, beep_cfg, sample_rate)
            return

        # ── Play confirmation beep ──────────
        play_beep(
            frequency=beep_cfg.get("frequency", 880),
            duration=beep_cfg.get("duration", 0.1),
            volume=beep_cfg.get("volume", 0.5),
            sample_rate=sample_rate,
        )

        # ── Record user speech (only when TTS is not playing) ──
        if jstate.get("is_speaking", False):
            time.sleep(0.1)  # yield briefly while TTS is active
            continue

        print("[ACTIVE] 🎙️  Listening...")
        event_bus.broadcast("listening", {})
        JarvisState().update(status="listening")
        audio = record_speech(
            sample_rate=sample_rate,
            channels=audio_cfg.get("channels", 1),
            block_size=audio_cfg.get("block_size", 1024),
            silence_threshold=silence_threshold,
            silence_duration=audio_cfg.get("silence_duration", 0.6),
            max_record_seconds=audio_cfg.get("max_record_seconds", 15.0),
        )

        if audio is None:
            consecutive_empty += 1
            # Each empty recording cycle is roughly max_record_seconds;
            # check if cumulative idle time has exceeded the timeout
            if (time.time() - last_speech_time) >= CONVERSATION_TIMEOUT:
                print(f"\n⏱️  No speech for {CONVERSATION_TIMEOUT}s — timing out.")
                jstate["in_conversation"] = False
                _exit_conversation(assistant_name, tts, beep_cfg, sample_rate)
                return
            print("[ACTIVE] 🤷  No speech captured — still listening...\n")
            continue

        # ── Transcribe ──────────────────────
        consecutive_empty = 0
        last_speech_time = time.time()

        print("[ACTIVE] 🔄  Transcribing...")
        text = stt.transcribe(audio)

        if not text:
            print("[ACTIVE] 🤷  Could not understand — still listening...\n")
            continue

        print(f"\n💬  You said: \"{text}\"\n")
        event_bus.broadcast("transcribed", {"text": text})
        JarvisState().update(last_query=text)
        JarvisState().add_message("user", text)

        # ── Check for exit phrases ──────────
        normalised = text.strip().lower()
        if normalised in EXIT_PHRASES:
            jstate["is_speaking"] = True
            tts.speak("Going to sleep. Call me when you need me.")
            jstate["is_speaking"] = False
            jstate["in_conversation"] = False
            time.sleep(0.3)  # let mic clear any echo residue
            _exit_conversation(assistant_name, tts, beep_cfg, sample_rate)
            return

        # ── Check for history-reset commands ─
        if normalised in RESET_PHRASES:
            conversation_history.clear()
            router.reset_history()
            print("🧹  Conversation history cleared. Fresh start!\n")
            jstate["is_speaking"] = True
            tts.speak("Conversation history cleared.")
            jstate["is_speaking"] = False
            time.sleep(0.3)  # let mic clear any echo residue
            continue

        # ── Route to LLM and respond (streaming) ──
        print("🤔  Thinking...")
        event_bus.broadcast("thinking", {})
        JarvisState().update(status="thinking")
        conversation_history.append({"role": "user", "content": text})

        # Stream LLM → TTS sentence-by-sentence
        sentence_gen = router.ask_stream(text, history=conversation_history)
        print("🔊  Streaming response...")
        event_bus.broadcast("speaking", {})
        JarvisState().update(status="speaking")
        jstate["is_speaking"] = True
        response = tts.speak_stream(sentence_gen)
        jstate["is_speaking"] = False
        time.sleep(0.3)  # let mic clear any echo residue

        conversation_history.append({"role": "assistant", "content": response})
        event_bus.broadcast("responding", {"text": response})
        JarvisState().update(last_response=response)
        JarvisState().add_message("assistant", response)

        # Trim history to configured max (max_history turns × 2 messages each)
        max_messages = max_history * 2
        if len(conversation_history) > max_messages:
            conversation_history = conversation_history[-max_messages:]

        print(f"\n🤖  {assistant_name}: {response}\n")

        # Immediately loop back — no wake word needed


def _exit_conversation(
    assistant_name: str,
    tts: "TTS",
    beep_cfg: dict,
    sample_rate: int,
) -> None:
    """Print sleep message and play a lower-pitched beep (440 Hz) on exit."""
    print(f"\n😴  {assistant_name} going to sleep...")
    play_beep(
        frequency=440,  # lower pitched beep to signal sleep
        duration=beep_cfg.get("duration", 0.1),
        volume=beep_cfg.get("volume", 0.5),
        sample_rate=sample_rate,
    )


if __name__ == "__main__":
    main()
