/**
 * hooks/useJarvis.ts — WebSocket hook for Jarvis events
 *
 * Connects to ws://localhost:8765/ws, auto-reconnects every 3s,
 * and parses incoming JSON events into React state.
 */

import { useState, useEffect } from "react";

export type JarvisStatus =
  | "idle"
  | "listening"
  | "thinking"
  | "speaking"
  | "wake_detected";

export interface SystemInfo {
  cpu: number;
  ram: number;
  battery: number;
}

export interface WorldMonitorData {
  type: string;
  payload: Record<string, any>;
}

export interface ProactiveAlert {
  type: string;
  message: string;
  severity: "info" | "warning" | "critical";
}

export interface JarvisState {
  status: JarvisStatus;
  lastQuery: string;
  lastResponse: string;
  systemInfo: SystemInfo;
  isConnected: boolean;
  skillMatched: string;
  worldMonitor: WorldMonitorData;
  dashboardOpen: boolean;
  expandedNewsIndex: number | null;
  proactiveAlert: ProactiveAlert | null;
}

const INITIAL_STATE: JarvisState = {
  status: "idle",
  lastQuery: "",
  lastResponse: "",
  systemInfo: { cpu: 0, ram: 0, battery: 0 },
  isConnected: false,
  skillMatched: "",
  worldMonitor: { type: "idle", payload: {} },
  dashboardOpen: false,
  expandedNewsIndex: null,
  proactiveAlert: null,
};

const WS_URL = "ws://localhost:8765/ws";
const RECONNECT_INTERVAL = 3000;

export function useJarvis(): JarvisState {
  const [state, setState] = useState<JarvisState>(INITIAL_STATE);
  const alertTimerRef = { current: null as ReturnType<typeof setTimeout> | null };

  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setInterval> | null = null;
    let alive = true;

    function connect() {
      if (!alive) return;

      try {
        ws = new WebSocket(WS_URL);

        ws.onopen = () => {
          setState((s) => ({ ...s, isConnected: true }));
          if (reconnectTimer) {
            clearInterval(reconnectTimer);
            reconnectTimer = null;
          }
        };

        ws.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data);
            handleEvent(msg);
          } catch {
            // ignore malformed messages
          }
        };

        ws.onclose = () => {
          setState((s) => ({ ...s, isConnected: false }));
          scheduleReconnect();
        };

        ws.onerror = () => {
          ws?.close();
        };
      } catch {
        scheduleReconnect();
      }
    }

    function scheduleReconnect() {
      if (alive && !reconnectTimer) {
        reconnectTimer = setInterval(connect, RECONNECT_INTERVAL);
      }
    }

    function handleEvent(msg: { event: string; data?: Record<string, any> }) {
      const data = msg.data || {};

      setState((s) => {
        switch (msg.event) {
          case "idle":
            return { ...s, status: "idle" as const };

          case "wake_detected":
            return { ...s, status: "wake_detected" as const };

          case "listening":
            return { ...s, status: "listening" as const };

          case "transcribed":
            return { ...s, lastQuery: data.text || "" };

          case "thinking":
            return { ...s, status: "thinking" as const };

          case "skill_matched":
            return { ...s, skillMatched: data.skill || "" };

          case "responding":
            return { ...s, lastResponse: data.text || "" };

          case "speaking":
            return { ...s, status: "speaking" as const };

          case "system_info":
            return {
              ...s,
              systemInfo: {
                cpu: data.cpu ?? 0,
                ram: data.ram ?? 0,
                battery: data.battery ?? 0,
              },
            };

          case "error":
            console.error("[Jarvis]", data.message);
            return s;

          case "content_update":
            return {
              ...s,
              worldMonitor: {
                type: data.type || "idle",
                payload: data.payload || {},
              },
            };

          case "open_dashboard":
            return { ...s, dashboardOpen: true, expandedNewsIndex: null };

          case "close_dashboard":
            return { ...s, dashboardOpen: false, expandedNewsIndex: null };

          case "expand_news":
            return { ...s, expandedNewsIndex: data.index ?? null };

          case "proactive_alert":
            // Auto-dismiss after 5 seconds
            if (alertTimerRef.current) {
              clearTimeout(alertTimerRef.current);
            }
            alertTimerRef.current = setTimeout(() => {
              setState((prev) => ({ ...prev, proactiveAlert: null }));
              alertTimerRef.current = null;
            }, 5000);
            return {
              ...s,
              proactiveAlert: {
                type: data.type || "info",
                message: data.message || "",
                severity: data.severity || "info",
              },
            };

          default:
            return s;
        }
      });
    }

    connect();

    return () => {
      alive = false;
      if (ws) ws.close();
      if (reconnectTimer) clearInterval(reconnectTimer);
    };
  }, []);

  return state;
}
