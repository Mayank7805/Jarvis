/**
 * App.tsx — Main Application Layout
 *
 * Assembles the full HUD: titlebar, status bar, orb + waveform,
 * response panel, and the full-height World Monitor dashboard.
 *
 * Layout: 45/55 horizontal split between main content and World Monitor.
 * System stats are now embedded inside WorldMonitor (no bottom bar).
 */

import React, { useState, useEffect, useCallback } from "react";
import { useJarvis } from "./hooks/useJarvis";
import { StatusBar } from "./components/StatusBar";
import { Orb } from "./components/Orb";
import { Waveform } from "./components/Waveform";
import { ResponsePanel } from "./components/ResponsePanel";
import { WorldMonitor } from "./components/WorldMonitor";
import { WorldDashboard } from "./screens/WorldDashboard";

// Type for the electronAPI exposed via preload
declare global {
  interface Window {
    electronAPI?: {
      minimize: () => void;
      close: () => void;
      toggleAlwaysOnTop: () => void;
      onAlwaysOnTopChanged: (cb: (value: boolean) => void) => void;
      openDashboard: () => void;
      closeDashboard: () => void;
    };
  }
}

export function App() {
  const jarvis = useJarvis();
  const [pinned, setPinned] = useState(false);

  useEffect(() => {
    window.electronAPI?.onAlwaysOnTopChanged?.((value: boolean) => {
      setPinned(value);
    });
  }, []);

  // Handle dashboard open/close with Electron fullscreen
  useEffect(() => {
    if (jarvis.dashboardOpen) {
      window.electronAPI?.openDashboard?.();
    } else {
      window.electronAPI?.closeDashboard?.();
    }
  }, [jarvis.dashboardOpen]);

  const handleCloseDashboard = useCallback(() => {
    // Send close event back to Python via WebSocket or direct state update
    // The WebSocket handler in useJarvis will pick up the close_dashboard event
    window.electronAPI?.closeDashboard?.();
    // Also send via the REST API to broadcast the event
    fetch("http://localhost:8765/command", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: "close dashboard" }),
    }).catch(() => {});
  }, []);

  return (
    <div className="app-container">
      {/* Full-Screen World Dashboard Overlay */}
      <WorldDashboard
        isOpen={jarvis.dashboardOpen}
        expandedIndex={jarvis.expandedNewsIndex}
        onClose={handleCloseDashboard}
      />

      {/* Custom frameless titlebar */}
      <div className="titlebar">
        <div className="titlebar-drag" />
        <div className="titlebar-controls">
          <button
            className={`titlebar-btn pin ${pinned ? "active" : ""}`}
            onClick={() => window.electronAPI?.toggleAlwaysOnTop()}
            title={pinned ? "Unpin from top" : "Pin on top"}
          >
            📌
          </button>
          <button
            className="titlebar-btn minimize"
            onClick={() => window.electronAPI?.minimize()}
            title="Minimize"
          >
            ─
          </button>
          <button
            className="titlebar-btn close"
            onClick={() => window.electronAPI?.close()}
            title="Hide to tray"
          >
            ✕
          </button>
        </div>
      </div>

      <StatusBar
        isConnected={jarvis.isConnected}
        skillMatched={jarvis.skillMatched}
        proactiveAlert={jarvis.proactiveAlert}
      />

      {/* ── 45/55 Split Layout (no bottom bar) ── */}
      <div className="hud-split">
        {/* Left panel: Orb, Waveform, Response */}
        <div className="left-panel">
          <div className="main-content">
            <Orb status={jarvis.status} />
            <Waveform status={jarvis.status} />
          </div>

          <ResponsePanel
            lastQuery={jarvis.lastQuery}
            lastResponse={jarvis.lastResponse}
          />
        </div>

        {/* Thin cyan vertical divider */}
        <div className="hud-divider" />

        {/* Right panel: World Monitor full dashboard */}
        <div className="right-panel">
          <WorldMonitor
            data={jarvis.worldMonitor}
            systemInfo={jarvis.systemInfo}
            status={jarvis.status}
          />
        </div>
      </div>
    </div>
  );
}
