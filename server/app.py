"""
server/app.py — FastAPI + WebSocket Server for Jarvis

Provides:
    • WebSocket endpoint (ws://localhost:8765/ws) for real-time events
    • REST endpoints for status, history, skills, and text commands
    • Background task that broadcasts system_info every 5 seconds

Started as a daemon thread from main.py — does NOT block the voice loop.
"""

import asyncio
import json
import logging

import psutil
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from server.jarvis_state import JarvisState
from server.event_bus import event_bus

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
#  FastAPI App
# ──────────────────────────────────────────────

app = FastAPI(
    title="Jarvis API",
    description="Real-time WebSocket events and REST API for the Jarvis voice assistant.",
    version="1.0.0",
)

# CORS — allow Electron and local dev frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared state singleton
state = JarvisState()


# ──────────────────────────────────────────────
#  WebSocket Connection Manager
# ──────────────────────────────────────────────

class ConnectionManager:
    """Manages multiple concurrent WebSocket clients."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a new WebSocket client."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a disconnected client."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, event: dict) -> None:
        """Send a JSON event to every connected client."""
        dead: list[WebSocket] = []
        message = json.dumps(event)

        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                dead.append(connection)

        # Clean up dead connections
        for conn in dead:
            self.disconnect(conn)


manager = ConnectionManager()


# ──────────────────────────────────────────────
#  Startup: wire EventBus ↔ ConnectionManager
# ──────────────────────────────────────────────

@app.on_event("startup")
async def on_startup() -> None:
    """Register the running event loop and manager with the EventBus."""
    loop = asyncio.get_running_loop()
    event_bus.set_loop(loop)
    event_bus.set_manager(manager)
    logger.info("EventBus wired to WebSocket manager.")

    # Start the system-info broadcaster
    asyncio.create_task(_system_info_broadcaster())


async def _system_info_broadcaster() -> None:
    """Broadcast CPU / RAM / battery stats every 5 seconds."""
    while True:
        try:
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent

            battery = psutil.sensors_battery()
            bat_pct = int(battery.percent) if battery else -1

            await manager.broadcast({
                "event": "system_info",
                "data": {
                    "cpu": cpu,
                    "ram": ram,
                    "battery": bat_pct,
                },
            })
        except Exception as e:
            logger.debug(f"system_info broadcast error: {e}")

        await asyncio.sleep(5)


# ──────────────────────────────────────────────
#  WebSocket Endpoint
# ──────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """
    Real-time event stream.

    Clients connect and receive JSON events pushed by the voice loop.
    The server also accepts incoming messages (for future bidirectional use).
    """
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive; handle any client-sent messages
            data = await websocket.receive_text()
            # Echo acknowledgement (useful for heartbeats / ping)
            await websocket.send_text(json.dumps({"event": "ack", "data": data}))
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ──────────────────────────────────────────────
#  REST Endpoints
# ──────────────────────────────────────────────

@app.get("/status")
async def get_status() -> dict:
    """Return Jarvis's current operational state."""
    return state.get_state()


@app.get("/history")
async def get_history(count: int = 10) -> list[dict]:
    """Return the last *count* conversation messages."""
    return state.get_history(count)


@app.get("/skills")
async def get_skills() -> dict:
    """Return the list of all loaded skills."""
    return {"skills": state.skills}


class CommandRequest(BaseModel):
    """Body schema for the /command endpoint."""
    text: str


@app.post("/command")
async def post_command(cmd: CommandRequest) -> dict:
    """
    Accept a text command as if the user spoke it.

    The actual processing is delegated to the voice loop
    via the event bus — we just record the intent here.
    """
    event_bus.broadcast("command_received", {"text": cmd.text})
    state.update(last_query=cmd.text, status="thinking")
    return {"status": "received", "text": cmd.text}


# ──────────────────────────────────────────────
#  Screenshot Serving (for World Monitor)
# ──────────────────────────────────────────────

@app.get("/screenshots/{filename}")
async def get_screenshot(filename: str):
    """
    Serve a screenshot image from data/screenshots/.

    Used by the World Monitor to display captured screenshots
    without needing file:// protocol (CSP-safe).
    """
    from fastapi.responses import FileResponse
    from pathlib import Path

    screenshots_dir = Path("data") / "screenshots"
    filepath = screenshots_dir / filename

    if not filepath.exists() or not filepath.is_file():
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"error": "Screenshot not found"})

    return FileResponse(str(filepath), media_type="image/png")


# ──────────────────────────────────────────────
#  World Dashboard Data (combined endpoint)
# ──────────────────────────────────────────────

@app.get("/world-data")
async def get_world_data() -> dict:
    """
    Return combined world intelligence data for the dashboard.

    Aggregates: top headlines, sports, market data, weather.
    All data is cached server-side to respect API rate limits.
    """
    from skills.world_briefing import get_world_data as fetch_world_data
    return fetch_world_data()


# ──────────────────────────────────────────────
#  Server Launcher (called from main.py thread)
# ──────────────────────────────────────────────

def start_server(host: str = "0.0.0.0", port: int = 8765) -> None:
    """
    Run the uvicorn server.

    Called inside a daemon thread from main.py so it doesn't
    block the voice loop.
    """
    import uvicorn

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="warning",  # keep console clean for Jarvis output
    )
