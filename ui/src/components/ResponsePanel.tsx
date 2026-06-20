/**
 * components/ResponsePanel.tsx — Query / Response Display
 *
 * Two-column panel:
 *   Left  → "YOU:"    last transcribed query
 *   Right → "JARVIS:" last response
 *
 * Uses framer-motion fade-in when new text appears.
 */

import React from "react";
import { motion, AnimatePresence } from "framer-motion";

interface ResponsePanelProps {
  lastQuery: string;
  lastResponse: string;
}

export function ResponsePanel({ lastQuery, lastResponse }: ResponsePanelProps) {
  return (
    <div className="response-panel">
      {/* User query */}
      <div className="response-section">
        <div className="response-section__label response-section__label--user">
          YOU
        </div>
        <AnimatePresence mode="wait">
          <motion.div
            key={lastQuery || "empty-q"}
            className={
              lastQuery
                ? "response-section__text response-section__text--user"
                : "response-section__placeholder"
            }
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.25 }}
          >
            {lastQuery || "Waiting for input..."}
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Jarvis response */}
      <div className="response-section">
        <div className="response-section__label response-section__label--jarvis">
          JARVIS
        </div>
        <AnimatePresence mode="wait">
          <motion.div
            key={lastResponse || "empty-r"}
            className={
              lastResponse
                ? "response-section__text response-section__text--jarvis"
                : "response-section__placeholder"
            }
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.25 }}
          >
            {lastResponse || "Standing by..."}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
