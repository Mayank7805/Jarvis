/**
 * components/Waveform.tsx — Audio Waveform Bars
 *
 * 20 vertical bars that animate based on Jarvis state:
 *   IDLE      → barely visible, minimal height
 *   LISTENING → random heights, cyan color
 *   SPEAKING  → wave pattern, green color
 *   THINKING  → subtle bounce, yellow color
 */

import React, { useState, useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { JarvisStatus } from "../hooks/useJarvis";

interface WaveformProps {
  status: JarvisStatus;
}

const BAR_COUNT = 20;
const UPDATE_INTERVAL = 100; // ms

const COLORS: Record<string, string> = {
  idle: "rgba(0,212,255,0.15)",
  listening: "rgba(0,212,255,0.7)",
  thinking: "rgba(255,170,0,0.6)",
  speaking: "rgba(0,255,136,0.7)",
  wake_detected: "rgba(0,212,255,0.8)",
};

function generateHeights(status: JarvisStatus, tick: number): number[] {
  const heights: number[] = [];

  for (let i = 0; i < BAR_COUNT; i++) {
    switch (status) {
      case "idle":
        heights.push(3 + Math.random() * 3);
        break;

      case "listening":
        heights.push(5 + Math.random() * 35);
        break;

      case "speaking":
        // Sine wave pattern that shifts with tick
        heights.push(
          8 + Math.abs(Math.sin((i + tick * 0.5) * 0.4)) * 32
        );
        break;

      case "thinking":
        // Gentle bounce
        heights.push(
          6 + Math.abs(Math.sin((i + tick * 0.3) * 0.5)) * 15
        );
        break;

      case "wake_detected":
        heights.push(10 + Math.random() * 30);
        break;

      default:
        heights.push(4);
    }
  }
  return heights;
}

export function Waveform({ status }: WaveformProps) {
  const [heights, setHeights] = useState<number[]>(
    () => new Array(BAR_COUNT).fill(4)
  );
  const tickRef = useRef(0);

  useEffect(() => {
    const interval = setInterval(() => {
      tickRef.current += 1;
      setHeights(generateHeights(status, tickRef.current));
    }, UPDATE_INTERVAL);

    return () => clearInterval(interval);
  }, [status]);

  const color = COLORS[status] || COLORS.idle;

  return (
    <div className="waveform">
      {heights.map((h, i) => (
        <motion.div
          key={i}
          className="waveform-bar"
          animate={{ height: h }}
          transition={{ duration: 0.1, ease: "easeOut" }}
          style={{ background: color }}
        />
      ))}
    </div>
  );
}
