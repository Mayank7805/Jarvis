/**
 * components/SystemStats.tsx — Bottom System Stats Bar
 *
 * Displays CPU%, RAM%, Battery%, and current status label.
 * Color-coded: green <60%, yellow 60-80%, red >80%.
 */

import React from "react";
import { SystemInfo, JarvisStatus } from "../hooks/useJarvis";

interface SystemStatsProps {
  systemInfo: SystemInfo;
  status: JarvisStatus;
}

function valueColor(value: number): string {
  if (value < 60) return "green";
  if (value < 80) return "yellow";
  return "red";
}

function batteryColor(value: number): string {
  if (value < 0) return "yellow"; // unknown
  if (value > 40) return "green";
  if (value > 15) return "yellow";
  return "red";
}

const STATUS_DISPLAY: Record<JarvisStatus, { label: string; color: string }> = {
  idle:          { label: "IDLE",      color: "#00d4ff" },
  listening:     { label: "LISTENING", color: "#00d4ff" },
  thinking:      { label: "THINKING",  color: "#ffaa00" },
  speaking:      { label: "SPEAKING",  color: "#00ff88" },
  wake_detected: { label: "ACTIVE",    color: "#00d4ff" },
};

export function SystemStats({ systemInfo, status }: SystemStatsProps) {
  const { cpu, ram, battery } = systemInfo;
  const statusInfo = STATUS_DISPLAY[status];

  return (
    <div className="system-stats">
      <div className="stat-item">
        <span className="stat-label">CPU</span>
        <span className={`stat-value ${valueColor(cpu)}`}>
          {cpu.toFixed(0)}%
        </span>
      </div>

      <div className="stat-divider" />

      <div className="stat-item">
        <span className="stat-label">RAM</span>
        <span className={`stat-value ${valueColor(ram)}`}>
          {ram.toFixed(0)}%
        </span>
      </div>

      <div className="stat-divider" />

      <div className="stat-item">
        <span className="stat-label">BAT</span>
        <span className={`stat-value ${batteryColor(battery)}`}>
          {battery >= 0 ? `${battery}%` : "N/A"}
        </span>
      </div>

      <div className="stat-divider" />

      <div className="stat-item">
        <span className="stat-label">STATUS</span>
        <span className="stat-status" style={{ color: statusInfo.color }}>
          {statusInfo.label}
        </span>
      </div>
    </div>
  );
}
