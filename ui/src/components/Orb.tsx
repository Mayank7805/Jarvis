/**
 * components/Orb.tsx — Animated Central Orb
 *
 * Glowing circle that changes animation based on Jarvis's state:
 *   IDLE         → slow pulse, dim cyan
 *   LISTENING    → faster pulse, bright cyan, expanding rings
 *   THINKING     → rotating arc/spinner, yellow tint
 *   SPEAKING     → ripple waves outward, green tint
 *   WAKE_DETECTED → bright flash → listening
 */

import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { JarvisStatus } from "../hooks/useJarvis";

interface OrbProps {
  status: JarvisStatus;
}

// Color map for each status
const STATUS_COLORS: Record<JarvisStatus, { primary: string; glow: string }> = {
  idle:          { primary: "rgba(0,212,255,0.20)", glow: "rgba(0,212,255,0.15)" },
  listening:     { primary: "rgba(0,212,255,0.45)", glow: "rgba(0,212,255,0.40)" },
  thinking:      { primary: "rgba(255,170,0,0.40)", glow: "rgba(255,170,0,0.35)" },
  speaking:      { primary: "rgba(0,255,136,0.40)", glow: "rgba(0,255,136,0.35)" },
  wake_detected: { primary: "rgba(0,212,255,0.70)", glow: "rgba(0,212,255,0.60)" },
};

const STATUS_LABELS: Record<JarvisStatus, string> = {
  idle: "IDLE",
  listening: "LISTENING",
  thinking: "PROCESSING",
  speaking: "SPEAKING",
  wake_detected: "ACTIVATED",
};

const STATUS_BORDER: Record<JarvisStatus, string> = {
  idle:          "rgba(0,212,255,0.20)",
  listening:     "rgba(0,212,255,0.50)",
  thinking:      "rgba(255,170,0,0.50)",
  speaking:      "rgba(0,255,136,0.50)",
  wake_detected: "rgba(0,212,255,0.80)",
};

export function Orb({ status }: OrbProps) {
  const colors = STATUS_COLORS[status];
  const borderColor = STATUS_BORDER[status];

  return (
    <div className="orb-container">
      <div className="orb">
        {/* Expanding rings for listening */}
        <AnimatePresence>
          {status === "listening" && (
            <>
              {[160, 200, 240].map((size, i) => (
                <motion.div
                  key={`ring-${size}`}
                  className="orb-ring"
                  initial={{ width: 120, height: 120, opacity: 0.4 }}
                  animate={{
                    width: size,
                    height: size,
                    opacity: [0.3, 0.08, 0.3],
                  }}
                  transition={{
                    duration: 2,
                    delay: i * 0.3,
                    repeat: Infinity,
                    ease: "easeInOut",
                  }}
                  exit={{ opacity: 0 }}
                  style={{ borderColor: "rgba(0,212,255,0.15)" }}
                />
              ))}
            </>
          )}
        </AnimatePresence>

        {/* Rotating ring for thinking */}
        <AnimatePresence>
          {status === "thinking" && (
            <motion.div
              initial={{ opacity: 0, rotate: 0 }}
              animate={{ opacity: 1, rotate: 360 }}
              exit={{ opacity: 0 }}
              transition={{ rotate: { duration: 1.5, repeat: Infinity, ease: "linear" }, opacity: { duration: 0.3 } }}
              style={{
                position: "absolute",
                width: 150,
                height: 150,
                borderRadius: "50%",
                border: "2px solid transparent",
                borderTopColor: "rgba(255,170,0,0.6)",
                borderRightColor: "rgba(255,170,0,0.2)",
                top: "50%",
                left: "50%",
                transform: "translate(-50%, -50%)",
              }}
            />
          )}
        </AnimatePresence>

        {/* Ripple rings for speaking */}
        <AnimatePresence>
          {status === "speaking" && (
            <>
              {[0, 1, 2].map((i) => (
                <motion.div
                  key={`ripple-${i}`}
                  className="orb-ring"
                  initial={{ width: 120, height: 120, opacity: 0.5 }}
                  animate={{
                    width: 220,
                    height: 220,
                    opacity: 0,
                  }}
                  transition={{
                    duration: 2,
                    delay: i * 0.6,
                    repeat: Infinity,
                    ease: "easeOut",
                  }}
                  exit={{ opacity: 0 }}
                  style={{ borderColor: "rgba(0,255,136,0.25)" }}
                />
              ))}
            </>
          )}
        </AnimatePresence>

        {/* Core orb */}
        <motion.div
          className="orb-core"
          animate={{
            scale: status === "idle" ? [1, 1.04, 1] : status === "listening" ? [1, 1.08, 1] : 1,
            boxShadow: `0 0 40px ${colors.glow}, 0 0 80px ${colors.glow}, inset 0 0 30px ${colors.primary}`,
          }}
          transition={{
            scale: {
              duration: status === "idle" ? 3 : 1.2,
              repeat: Infinity,
              ease: "easeInOut",
            },
            boxShadow: { duration: 0.5 },
          }}
          style={{
            background: `radial-gradient(circle at 35% 35%, ${colors.primary}, transparent 70%)`,
            borderColor: borderColor,
          }}
        />

        {/* Flash for wake_detected */}
        <AnimatePresence>
          {status === "wake_detected" && (
            <motion.div
              initial={{ opacity: 0.8, scale: 1 }}
              animate={{ opacity: 0, scale: 2 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.6 }}
              style={{
                position: "absolute",
                width: 120,
                height: 120,
                borderRadius: "50%",
                background: "rgba(0,212,255,0.3)",
                top: "50%",
                left: "50%",
                transform: "translate(-50%, -50%)",
              }}
            />
          )}
        </AnimatePresence>
      </div>

      <motion.div
        className="orb-label"
        animate={{ opacity: [0.5, 1, 0.5] }}
        transition={{ duration: 2, repeat: Infinity }}
        style={{
          color: borderColor,
        }}
      >
        {STATUS_LABELS[status]}
      </motion.div>
    </div>
  );
}
