/**
 * components/StatusBar.tsx — Top HUD Status Bar + Proactive Alert Banner
 *
 * Left:   J.A.R.V.I.S logo in cyan
 * Center: connection indicator + skill badge
 * Right:  live clock (HH:MM:SS)
 *
 * Below the bar: slide-down alert banner for proactive system alerts
 * (battery, RAM, CPU, break reminders, etc.)
 */

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { ProactiveAlert } from "../hooks/useJarvis";

/** Map alert types to emoji icons */
const ALERT_ICONS: Record<string, string> = {
  battery_critical: "🔋",
  battery_low: "🔋",
  battery_full: "🔌",
  ram_high: "💾",
  ram_critical: "💾",
  cpu_high: "🔥",
  break_reminder: "☕",
  midnight_alert: "🌙",
  morning_checkin: "🌅",
  afternoon_checkin: "☀️",
  evening_checkin: "🌆",
};

interface StatusBarProps {
  isConnected: boolean;
  skillMatched: string;
  proactiveAlert: ProactiveAlert | null;
}

export function StatusBar({ isConnected, skillMatched, proactiveAlert }: StatusBarProps) {
  const [time, setTime] = useState(formatTime());

  useEffect(() => {
    const interval = setInterval(() => setTime(formatTime()), 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <>
      <div className="status-bar">
        {/* Left: Logo */}
        <div className="status-bar__logo">J.A.R.V.I.S</div>

        {/* Center: Connection + Skill */}
        <div className="status-bar__center">
          <div
            className={`connection-dot ${
              isConnected ? "connected" : "disconnected"
            }`}
          />
          <span className="connection-label">
            {isConnected ? "ONLINE" : "OFFLINE"}
          </span>

          <AnimatePresence>
            {skillMatched && (
              <motion.span
                className="skill-badge"
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 10 }}
                transition={{ duration: 0.3 }}
              >
                {skillMatched}
              </motion.span>
            )}
          </AnimatePresence>
        </div>

        {/* Right: Clock */}
        <div className="status-bar__time">{time}</div>
      </div>

      {/* ── Proactive Alert Banner ── */}
      <AnimatePresence>
        {proactiveAlert && (
          <motion.div
            className={`proactive-alert proactive-alert--${proactiveAlert.severity}`}
            initial={{ height: 0, opacity: 0, y: -10 }}
            animate={{ height: "auto", opacity: 1, y: 0 }}
            exit={{ height: 0, opacity: 0, y: -10 }}
            transition={{ duration: 0.35, ease: "easeOut" }}
          >
            <span className="proactive-alert__icon">
              {ALERT_ICONS[proactiveAlert.type] || "🔔"}
            </span>
            <span className="proactive-alert__message">
              {proactiveAlert.message}
            </span>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

function formatTime(): string {
  const now = new Date();
  return now.toLocaleTimeString("en-US", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}
