<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Electron-33-47848F?style=for-the-badge&logo=electron&logoColor=white" />
  <img src="https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=black" />
  <img src="https://img.shields.io/badge/Gemini_2.5-Flash-4285F4?style=for-the-badge&logo=google&logoColor=white" />
  <img src="https://img.shields.io/badge/Platform-Windows_11-0078D4?style=for-the-badge&logo=windows&logoColor=white" />
</p>

<h1 align="center">
  🤖 J.A.R.V.I.S — AI Voice Assistant
</h1>

<p align="center">
  <b>A real-time, voice-activated AI assistant for Windows with an Iron Man–inspired HUD,<br/>
  powered by Gemini 2.5 Flash, Whisper STT, and a modular skill engine.</b>
</p>

<p align="center">
  <i>"All systems nominal."</i>
</p>

---

## ✨ Highlights

- 🎙️ **Hands-free voice control** — say *"Hey Jarvis"* or double-clap to activate
- 🧠 **Dual LLM brain** — Gemini 2.5 Flash (cloud) with Ollama (local CPU) fallback
- 🛠️ **Agentic execution** — Gemini function-calling opens apps, types text, runs commands, writes files
- 🔊 **Streaming TTS** — sentence-by-sentence speech via Microsoft Edge Neural voices
- 🌍 **Iron Man HUD** — Electron + React desktop UI with live world map, news ticker, and system stats
- 💾 **Long-term memory** — ChromaDB vector store with semantic search across conversations
- ⚡ **14 built-in skills** — weather, news, music, email, screenshots, timers, calculator, and more
- 👁️ **Proactive monitor** — battery/RAM/CPU alerts, break reminders, and time-based check-ins

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      main.py (Entry Point)                   │
│  Wake Word → Record → Transcribe → Route → Speak → Repeat   │
└──────────────┬──────────────────────┬────────────────────────┘
               │                      │
    ┌──────────▼──────────┐  ┌────────▼────────────────────┐
    │   core/              │  │   llm/                      │
    │  ├─ wake_word.py     │  │  ├─ router.py (LLMRouter)   │
    │  ├─ audio_capture.py │  │  ├─ gemini_client.py        │
    │  ├─ stt.py (Whisper) │  │  └─ ollama_client.py        │
    │  ├─ tts.py (Edge)    │  └───────────────────────────────┘
    │  ├─ memory.py        │
    │  ├─ agent_executor   │  ┌───────────────────────────────┐
    │  ├─ briefing.py      │  │   skills/                    │
    │  └─ proactive_monitor│  │  ├─ skill_manager.py         │
    └─────────────────────┘  │  ├─ weather.py  ├─ news.py   │
                              │  ├─ music.py    ├─ email.py  │
    ┌─────────────────────┐  │  ├─ timer.py    ├─ notes.py  │
    │   server/            │  │  ├─ calculator  ├─ clipboard │
    │  ├─ app.py (FastAPI) │  │  ├─ screenshot  ├─ sys_ctrl  │
    │  ├─ event_bus.py     │  │  └─ system_info ├─ world_brf │
    │  └─ jarvis_state.py  │  └───────────────────────────────┘
    └──────────┬──────────┘
               │ WebSocket (ws://localhost:8765/ws)
    ┌──────────▼──────────┐
    │   ui/ (Electron)     │
    │  ├─ App.tsx (HUD)    │
    │  ├─ Orb + Waveform   │
    │  ├─ WorldMonitor     │
    │  ├─ WorldDashboard   │
    │  └─ SystemStats      │
    └─────────────────────┘
```

### Request Routing Pipeline

Every user query flows through a priority chain — the first handler that matches wins:

| Priority | Handler | Latency | Description |
|:---:|---|---|---|
| 1 | **Skill Engine** | ~0 ms | Pattern-matched local skills (timer, calculator, notes, etc.) |
| 2 | **Weather API** | ~200 ms | Direct OpenWeatherMap call — no LLM involved |
| 3 | **News API** | ~300 ms | Direct NewsAPI call for headlines |
| 4 | **World Dashboard** | ~500 ms | Aggregated intelligence dashboard (news + weather + markets) |
| 5 | **Agent Executor** | ~1 s | Gemini function-calling (open apps, run commands, type, etc.) |
| 6 | **Gemini Chat** | ~1–3 s | Cloud LLM for general conversation (streaming) |
| 7 | **Ollama Fallback** | ~2–5 s | Local LLM when offline |

---

## 🚀 Quick Start

### Prerequisites

- **Windows 10/11** (required for Edge TTS, system controls, and pyautogui)
- **Python 3.11+**
- **Node.js 18+** & npm
- **Microphone** (for voice input)
- *(Optional)* [Ollama](https://ollama.ai) — for offline LLM fallback

### 1. Clone the Repository

```bash
git clone https://github.com/Mayank7805/Jarvis.git
cd Jarvis
```

### 2. Set Up Python Environment

```bash
python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt
```

<details>
<summary><b>📦 Key Python Dependencies</b></summary>

| Package | Purpose |
|---|---|
| `google-genai` | Gemini 2.5 Flash API client |
| `faster-whisper` | Speech-to-text (Whisper) |
| `openwakeword` | "Hey Jarvis" wake word detection |
| `edge-tts` | Microsoft Edge Neural TTS |
| `chromadb` | Vector database for long-term memory |
| `sentence-transformers` | Embeddings for semantic search |
| `sounddevice` | Real-time audio capture |
| `pygame` | Audio playback for TTS |
| `psutil` | System monitoring (CPU, RAM, battery) |
| `fastapi` + `uvicorn` | WebSocket/REST server |
| `pyautogui` | Keyboard/mouse automation |

</details>

### 3. Configure API Keys

Create a `.env` file in the project root:

```env
# Required
GEMINI_API_KEY=your_gemini_api_key_here

# Optional (enables weather & news skills)
OPENWEATHER_API_KEY=your_openweather_key_here
NEWS_API_KEY=your_newsapi_key_here

# Optional (enables email skill)
GMAIL_ADDRESS=your_email@gmail.com
GMAIL_APP_PASSWORD=your_app_password
```

> **Get your API keys:**
> - [Gemini API Key](https://aistudio.google.com/apikey) (free tier available)
> - [OpenWeatherMap](https://openweathermap.org/api) (free tier)
> - [NewsAPI](https://newsapi.org/) (free tier)
> - [Gmail App Password](https://support.google.com/accounts/answer/185833) (for email skill)

### 4. Install UI Dependencies

```bash
cd ui
npm install
cd ..
```

### 5. Launch Jarvis

**Option A — One-click launcher (recommended):**
```bash
launch_jarvis.bat
```
This starts both the Python backend and Electron UI in separate windows.

**Option B — Manual start:**

```bash
# Terminal 1: Python backend
venv\Scripts\activate
python main.py

# Terminal 2: Electron UI
cd ui
npm start
```

### 6. Start Talking!

Say **"Hey Jarvis"** or **double-clap** → the assistant enters conversation mode.

No wake word is needed between follow-up messages — just speak naturally.

Say **"goodbye"** or **"sleep"** to exit conversation mode.

---

## 🎯 Skills Reference

### Built-in Skills (instant, no LLM)

| Skill | Trigger Examples | Description |
|---|---|---|
| 🧮 **Calculator** | *"what's 15% of 240"*, *"square root of 144"* | Math expressions, percentages, unit conversions |
| ⏱️ **Timer** | *"set a timer for 5 minutes"*, *"set alarm for 3pm"* | Countdown timers with TTS alert on completion |
| 📝 **Notes** | *"take a note: buy milk"*, *"read my notes"* | Persistent text-file notes |
| 📋 **Clipboard** | *"copy this"*, *"what did I copy"*, *"paste"* | Read/write system clipboard |
| 📧 **Email** | *"send email to john@example.com"* | Compose and send via Gmail SMTP |
| 🎵 **Music** | *"play shape of you"*, *"pause music"* | YouTube search + playback control |
| 📸 **Screenshot** | *"take a screenshot"* | Screen capture saved to `data/screenshots/` |
| 🖥️ **System Info** | *"battery level"*, *"how much RAM"* | CPU, RAM, battery, disk stats |
| ⚙️ **System Control** | *"set volume to 50"*, *"lock the computer"* | Volume, brightness, shutdown, restart, lock, sleep |

### Agent-Powered Actions (Gemini function-calling)

| Tool | What It Does |
|---|---|
| `run_command` | Execute any Windows shell command (with safety blocklist) |
| `open_url` | Open any URL in the default browser |
| `type_text` | Type text at the current cursor position |
| `press_key` | Press keyboard shortcuts (e.g., Ctrl+C, Alt+F4) |
| `search_and_open` | Google search and open results |
| `write_to_file` | Create files on the Desktop |
| `take_action_with_code` | Execute Gemini-generated Python in a sandboxed environment |

### API-Powered Skills

| Skill | Source | Description |
|---|---|---|
| 🌤️ **Weather** | OpenWeatherMap | Real-time weather for any city |
| 📰 **News** | NewsAPI | Top headlines with category filtering |
| 🌍 **World Briefing** | Multiple APIs | Aggregated dashboard: news + weather + markets |

---

## 🖥️ The HUD (User Interface)

The Electron desktop app renders an **Iron Man–inspired heads-up display**:

```
┌─────────────────────────────────────────────────────────────┐
│  JARVIS                     ● CONNECTED               22:45│
├─────────────────────────┬───────────────────────────────────┤
│                         │  ◆ WORLD MONITOR                  │
│       ╭─────╮          │  ┌─────────────────────────────┐  │
│       │ ORB │          │  │     🌍 LIVE MAP              │  │
│       ╰─────╯          │  │     (Leaflet dark tiles)     │  │
│    ▁ ▃ ▅ ▇ ▅ ▃ ▁      │  ├─────────────────────────────┤  │
│      WAVEFORM           │  │  📰 NEWS │ 📰 NEWS         │  │
│                         │  │  📰 NEWS │ 📰 NEWS         │  │
│ ┌─────────┬───────────┐│  ├─────────────────────────────┤  │
│ │ USER    │ JARVIS    ││  │  LIVE FEED │ SYSTEM STATS   │  │
│ │ query   │ response  ││  │            │ CPU RAM BAT    │  │
│ └─────────┴───────────┘│  └─────────────────────────────┘  │
│                         │  ▸▸ TICKER: Breaking news...      │
└─────────────────────────┴───────────────────────────────────┘
```

**Key UI Features:**
- **Animated orb** — pulses with cyan/green/amber glow based on Jarvis state (idle/listening/thinking/speaking)
- **Real-time waveform** — visualizes audio activity
- **World Monitor** — live Leaflet map + 4-tile news grid + scrolling ticker
- **System stats** — CPU, RAM, battery gauges updated every 5 seconds
- **World Dashboard** — say *"what's happening in the world"* for a full-screen intelligence view
- **Proactive alert banners** — battery warnings, RAM alerts, break reminders
- **Frameless window** — custom titlebar with pin-on-top, minimize to tray
- **Global shortcut** — `Ctrl+Shift+J` to toggle the HUD from anywhere

---

## ⚙️ Configuration

All settings are in [`config/jarvis.yaml`](config/jarvis.yaml):

```yaml
assistant:
  name: "Jarvis"

activation:
  wake_words: ["hey jarvis"]
  clap_detection: true

stt:
  model: "tiny.en"          # Whisper model size (tiny/base/small/medium/large)
  device: "cpu"             # cpu or cuda
  compute_type: "int8"      # int8 (fastest) or float16

tts:
  voice: "en-US-GuyNeural"  # Microsoft Edge TTS voice
  rate: "+10%"              # Speech speed adjustment

llm:
  local_model: "phi3.5"         # Ollama model for offline use
  api_model: "gemini-2.5-flash" # Cloud LLM
  max_history: 10                # Conversation turns to remember

audio:
  sample_rate: 16000
  silence_duration: 0.7     # Seconds of silence before end-of-speech
  max_record_seconds: 20    # Safety cap on recording length
```

---

## 🧠 Memory System

Jarvis uses **ChromaDB** with **sentence-transformers** embeddings for persistent, semantic memory:

| Memory Type | Description | Example |
|---|---|---|
| **Episodic** | Every conversation turn is auto-saved | *"What did I ask you yesterday about Python?"* |
| **Semantic** | Explicit facts you tell Jarvis to remember | *"Remember that my birthday is March 15"* |

Memories are stored in `data/memory/` and persist across restarts. The LLM receives relevant past context automatically via semantic search.

---

## 👁️ Proactive Monitor

A background daemon that watches system state and speaks alerts without being asked:

| Alert | Trigger | Cooldown |
|---|---|---|
| 🔴 Battery Critical | ≤ 10%, not plugged in | 5 min |
| 🟡 Battery Low | ≤ 20%, not plugged in | 10 min |
| 🟢 Battery Full | 100%, plugged in | Once/day |
| 🔴 RAM Critical | ≥ 95% usage | 5 min |
| 🟡 RAM High | ≥ 90% usage | 5 min |
| 🟡 CPU Sustained High | ≥ 85% for 3+ checks | 3 min |
| 🔵 Break Reminder | 3+ hours continuous use | 3 hours |
| 🔵 Late Night | Working between 1–4 AM | Once/day |
| 🔵 Morning Briefing | 9:00 AM | Once/day |
| 🔵 Afternoon Check-in | 1:00 PM | Once/day |
| 🔵 Evening Weather | 6:00 PM | Once/day |

Alerts are **conversation-aware** — they never interrupt active speech or conversations.

---

## 📁 Project Structure

```
Jarvis/
├── main.py                  # Entry point — voice assistant loop
├── launch_jarvis.bat        # One-click launcher (backend + UI)
├── launch_jarvis.ps1        # PowerShell launcher variant
├── config/
│   └── jarvis.yaml          # All configuration settings
├── core/
│   ├── agent_executor.py    # Gemini function-calling engine (9 tools)
│   ├── audio_capture.py     # Microphone recording + clap detection
│   ├── briefing.py          # Morning briefing generator
│   ├── memory.py            # ChromaDB long-term memory
│   ├── proactive_monitor.py # Background system alerts
│   ├── stt.py               # Speech-to-text (faster-whisper)
│   ├── tts.py               # Text-to-speech (edge-tts + pygame)
│   └── wake_word.py         # "Hey Jarvis" detection (openwakeword)
├── llm/
│   ├── router.py            # Query routing engine (skills → agent → LLM)
│   ├── gemini_client.py     # Google Gemini API client (streaming)
│   └── ollama_client.py     # Ollama local LLM client (streaming)
├── skills/
│   ├── skill_manager.py     # Auto-discovery & routing
│   ├── base_skill.py        # Abstract base class for skills
│   ├── calculator.py        # Math, percentages, conversions
│   ├── clipboard.py         # System clipboard read/write
│   ├── email_skill.py       # Gmail SMTP email sending
│   ├── music.py             # YouTube music playback
│   ├── news.py              # NewsAPI headlines
│   ├── notes.py             # Persistent text notes
│   ├── screenshot.py        # Screen capture
│   ├── system_control.py    # Volume, brightness, power
│   ├── system_info.py       # CPU, RAM, battery, disk
│   ├── timer.py             # Countdown timers
│   ├── weather.py           # OpenWeatherMap integration
│   └── world_briefing.py    # Aggregated world intelligence
├── server/
│   ├── app.py               # FastAPI + WebSocket server
│   ├── event_bus.py         # Real-time event broadcasting
│   └── jarvis_state.py      # Shared state singleton
├── ui/
│   ├── electron/
│   │   ├── main.js          # Electron main process
│   │   └── preload.js       # Context bridge for IPC
│   ├── src/
│   │   ├── App.tsx          # Main HUD layout
│   │   ├── hooks/useJarvis.ts  # WebSocket state hook
│   │   ├── components/
│   │   │   ├── Orb.tsx      # Animated status orb
│   │   │   ├── Waveform.tsx # Audio waveform visualizer
│   │   │   ├── StatusBar.tsx
│   │   │   ├── ResponsePanel.tsx
│   │   │   ├── SystemStats.tsx
│   │   │   └── WorldMonitor.tsx  # Map + news + stats dashboard
│   │   └── screens/
│   │       └── WorldDashboard.tsx  # Full-screen intelligence view
│   └── styles/
│       ├── globals.css      # Iron Man HUD theme (1300+ lines)
│       └── world-dashboard.css
└── data/
    ├── memory/              # ChromaDB persistent storage
    ├── screenshots/         # Captured screenshots
    ├── notes.txt            # User notes
    └── logs/                # Application logs
```

---

## 🔌 Server API

The FastAPI server runs on `http://localhost:8765` alongside the voice loop:

| Endpoint | Method | Description |
|---|---|---|
| `/ws` | WebSocket | Real-time event stream (status, responses, alerts) |
| `/status` | GET | Current Jarvis state |
| `/history` | GET | Conversation history |
| `/skills` | GET | List of loaded skills |
| `/command` | POST | Send a text command (as if spoken) |
| `/world-data` | GET | Aggregated world intelligence data |
| `/screenshots/{file}` | GET | Serve screenshot images |

---

## 🗣️ Voice Commands Cheat Sheet

| Command | What It Does |
|---|---|
| *"Hey Jarvis"* / double-clap | Wake up and start listening |
| *"goodbye"* / *"sleep"* | Exit conversation mode |
| *"reset"* / *"clear history"* | Clear conversation memory |
| *"open Chrome"* / *"open VS Code"* | Launch applications |
| *"search for Python tutorials"* | Google search in browser |
| *"what's happening in the world"* | Open full-screen World Dashboard |
| *"close dashboard"* | Close the World Dashboard |
| *"tell me more about the first news"* | Expand a news story |
| *"set a timer for 10 minutes"* | Start a countdown timer |
| *"take a screenshot"* | Capture and save the screen |
| *"set volume to 50"* | Adjust system volume |
| *"lock the computer"* | Lock the workstation |
| *"what's the weather in Tokyo"* | Get current weather |
| *"battery level"* | Check battery percentage |

---

## 🛡️ Safety Features

- **Blocked commands** — destructive shell commands (`del`, `format`, `rm`, `rmdir`) are blocklisted
- **Sandboxed code execution** — `take_action_with_code` restricts to 10 safe modules and blocks `socket`, `requests`, `eval`, `exec`, and network access
- **Path sanitization** — file writes are confined to the Desktop with directory traversal prevention
- **Conversation-aware alerts** — proactive monitor never interrupts active speech

---

## 📄 License

This project is open-source. Feel free to fork, modify, and build upon it.

---

<p align="center">
  <b>Built with ❤️ by <a href="https://github.com/Mayank7805">Mayank</a></b><br/>
  <sub>Inspired by Tony Stark's J.A.R.V.I.S</sub>
</p>
