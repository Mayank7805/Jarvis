/**
 * components/WorldMonitor.tsx — Full Intelligence Dashboard
 *
 * Dense 3-section information panel:
 *   Section 1 (45%) — Interactive dark world map with geo markers
 *   Section 2 (30%) — Live news feed grid + scrolling ticker
 *   Section 3 (25%) — Live YouTube feed + system metrics
 */

import React, { useEffect, useRef, useState, useMemo, useCallback, Component } from "react";
import { motion } from "framer-motion";
import type { WorldMonitorData, SystemInfo, JarvisStatus } from "../hooks/useJarvis";
// Leaflet CSS is loaded via <link> tag in index.html

import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from "react-leaflet";

// ── Error Boundary ───────────────────────────────

class MapErrorBoundary extends Component<
  { children: React.ReactNode },
  { hasError: boolean; error: string }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: "" };
  }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error: error.message };
  }
  componentDidCatch(error: Error) {
    console.error("[WorldMonitor] Map error:", error);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="wm2-map-fallback">
          <span className="wm2-map-fallback__label">MAP OFFLINE</span>
          <span className="wm2-map-fallback__detail">{this.state.error}</span>
        </div>
      );
    }
    return this.props.children;
  }
}

// ── Types ────────────────────────────────────────

interface WorldMonitorProps {
  data: WorldMonitorData;
  systemInfo: SystemInfo;
  status: JarvisStatus;
}

interface GeoMarker {
  id: string;
  lat: number;
  lng: number;
  label: string;
  type: "base" | "conflict" | "positive" | "science";
  pulse?: boolean;
}

interface NewsHeadline {
  title: string;
  source: string;
  timestamp?: string;
}

// ── Static Base Markers ──────────────────────────

const BASE_MARKERS: GeoMarker[] = [
  { id: "newdelhi", lat: 28.6139, lng: 77.209, label: "NEW DELHI", type: "base", pulse: true },
  { id: "washington", lat: 38.9072, lng: -77.0369, label: "WASHINGTON DC", type: "base" },
  { id: "london", lat: 51.5074, lng: -0.1278, label: "LONDON", type: "base" },
  { id: "beijing", lat: 39.9042, lng: 116.4074, label: "BEIJING", type: "base" },
  { id: "moscow", lat: 55.7558, lng: 37.6173, label: "MOSCOW", type: "base" },
];

// ── Color Map ────────────────────────────────────

const MARKER_COLORS: Record<string, string> = {
  base: "#00d4ff",
  conflict: "#ff3366",
  positive: "#00ff88",
  science: "#4488ff",
};

const STATUS_COLORS: Record<JarvisStatus, string> = {
  idle: "#00d4ff",
  listening: "#00d4ff",
  thinking: "#ffaa00",
  speaking: "#00ff88",
  wake_detected: "#00d4ff",
};

// ── Clock Component ──────────────────────────────

function HeaderClock() {
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const utc = now.toUTCString().slice(17, 25);
  const local = now.toLocaleTimeString("en-IN", { hour12: false });

  return (
    <div className="wm2-header__clock">
      <span className="wm2-header__clock-utc">UTC {utc}</span>
      <span className="wm2-header__clock-sep">│</span>
      <span className="wm2-header__clock-local">IST {local}</span>
    </div>
  );
}

// ── Map Controller ───────────────────────────────

function MapDefaults() {
  const map = useMap();
  useEffect(() => {
    try {
      map.zoomControl?.remove();
      map.attributionControl?.setPrefix("");
    } catch (e) {
      // ignore
    }
  }, [map]);
  return null;
}

// ── Pulsing Circle Marker ────────────────────────

function PulsingMarker({ marker }: { marker: GeoMarker }) {
  const color = MARKER_COLORS[marker.type] || "#00d4ff";
  const isBase = marker.type === "base";
  const isHome = marker.id === "newdelhi";

  return (
    <>
      {/* Outer pulse ring */}
      <CircleMarker
        center={[marker.lat, marker.lng]}
        radius={isHome ? 10 : isBase ? 5 : 7}
        pathOptions={{
          color: color,
          fillColor: color,
          fillOpacity: 0.08,
          weight: 1,
          opacity: 0.3,
          className: marker.pulse ? "wm2-marker-pulse" : "",
        }}
      />
      {/* Inner dot */}
      <CircleMarker
        center={[marker.lat, marker.lng]}
        radius={isHome ? 4 : isBase ? 2 : 3}
        pathOptions={{
          color: color,
          fillColor: color,
          fillOpacity: isBase ? 0.4 : 0.8,
          weight: 1,
          opacity: isBase && !isHome ? 0.3 : 0.8,
        }}
      >
        <Popup className="wm2-map-popup">
          <span>{marker.label}</span>
        </Popup>
      </CircleMarker>
    </>
  );
}

// ── Map Section ──────────────────────────────────

function MapSection({ markers, flashSection }: { markers: GeoMarker[]; flashSection: string | null }) {
  return (
    <div className={`wm2-map ${flashSection === "map" ? "wm2-flash" : ""}`}>
      <MapErrorBoundary>
        <MapContainer
          center={[20, 0] as [number, number]}
          zoom={2}
          className="wm2-map__container"
          zoomControl={false}
          attributionControl={true}
          scrollWheelZoom={true}
          dragging={true}
          doubleClickZoom={false}
          minZoom={2}
          maxZoom={6}
          style={{ width: "100%", height: "100%", background: "#0a0a0f" }}
        >
          <MapDefaults />
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            attribution=""
          />
          {markers.map((marker: GeoMarker) => (
            <PulsingMarker key={marker.id} marker={marker} />
          ))}
        </MapContainer>
      </MapErrorBoundary>
      <div className="wm2-map__label">GLOBAL INTELLIGENCE OVERLAY</div>
    </div>
  );
}

// ── News Tile ────────────────────────────────────

function NewsTile({ headline, index }: { headline: NewsHeadline; index: number }) {
  return (
    <motion.div
      className="wm2-news__tile"
      initial={{ opacity: 0, x: 30 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.08, duration: 0.35, ease: "easeOut" }}
    >
      <span className="wm2-news__tile-source">{headline.source || "WIRE"}</span>
      <span className="wm2-news__tile-headline">{headline.title}</span>
      <span className="wm2-news__tile-time">
        {headline.timestamp || new Date().toLocaleTimeString("en-IN", { hour12: false })}
      </span>
    </motion.div>
  );
}

// ── Metric Bar ───────────────────────────────────

function MetricBar({ label, value, unit = "%" }: { label: string; value: number; unit?: string }) {
  const getColor = () => {
    if (value < 0) return "var(--text-dim)";
    if (value > 85) return "var(--accent-red)";
    if (value > 60) return "var(--accent-yellow)";
    return "var(--accent-green)";
  };

  const displayVal = value < 0 ? "N/A" : `${Math.round(value)}${unit}`;
  const barWidth = value < 0 ? 0 : Math.min(value, 100);

  return (
    <div className="wm2-metric">
      <div className="wm2-metric__header">
        <span className="wm2-metric__label">{label}</span>
        <span className="wm2-metric__value" style={{ color: getColor() }}>
          {displayVal}
        </span>
      </div>
      <div className="wm2-metric__bar-track">
        <motion.div
          className="wm2-metric__bar-fill"
          style={{ background: getColor(), boxShadow: `0 0 6px ${getColor()}` }}
          initial={{ width: 0 }}
          animate={{ width: `${barWidth}%` }}
          transition={{ duration: 0.8, ease: "easeOut" }}
        />
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════
//  MAIN COMPONENT
// ══════════════════════════════════════════════════

export function WorldMonitor({ data, systemInfo, status }: WorldMonitorProps) {
  const { type, payload } = data;
  const [dynamicMarkers, setDynamicMarkers] = useState<GeoMarker[]>([]);
  const [headlines, setHeadlines] = useState<NewsHeadline[]>([]);
  const [flashSection, setFlashSection] = useState<string | null>(null);

  // Process incoming content updates
  useEffect(() => {
    if (type === "news" && payload.headlines) {
      const newHeadlines: NewsHeadline[] = (payload.headlines as any[]).map((h: any) => ({
        title: h.title || "",
        source: h.source || "WIRE",
        timestamp: new Date().toLocaleTimeString("en-IN", { hour12: false }),
      }));
      setHeadlines(newHeadlines);

      // Generate dynamic markers from news content
      const newsMarkers = generateNewsMarkers(newHeadlines);
      setDynamicMarkers(newsMarkers);

      // Flash the news section
      triggerFlash("news");
    }

    if (type === "weather") {
      triggerFlash("map");
    }

    if (type === "system") {
      triggerFlash("stats");
    }
  }, [type, payload]);

  const triggerFlash = useCallback((section: string) => {
    setFlashSection(section);
    setTimeout(() => setFlashSection(null), 600);
  }, []);

  // Combine base + dynamic markers
  const allMarkers = useMemo(
    () => [...BASE_MARKERS, ...dynamicMarkers],
    [dynamicMarkers]
  );

  const statusColor = STATUS_COLORS[status] || "#00d4ff";
  const statusLabel = status.toUpperCase().replace("_", " ");

  return (
    <div className="wm2">
      {/* Scanline overlay for right panel */}
      <div className="wm2-scanline" />

      {/* ── Header ── */}
      <div className="wm2-header">
        <div className="wm2-header__title">
          <span className="wm2-header__diamond">◆</span>
          <span className="wm2-header__text">W O R L D &nbsp; M O N I T O R</span>
        </div>
        <HeaderClock />
      </div>

      {/* ── Section 1: World Map ── */}
      <MapSection markers={allMarkers} flashSection={flashSection} />

      {/* ── Section 2: News Feed ── */}
      <div className={`wm2-news ${flashSection === "news" ? "wm2-flash" : ""}`}>
        <div className="wm2-news__section-header">
          <span className="wm2-news__section-label">◆ LIVE FEED</span>
          <span className="wm2-news__count">{headlines.length} ITEMS</span>
        </div>
        <div className="wm2-news__grid">
          {(headlines.length > 0 ? headlines.slice(0, 4) : PLACEHOLDER_HEADLINES).map((h, i) => (
            <NewsTile key={`${h.title}-${i}`} headline={h} index={i} />
          ))}
        </div>
        {/* Scrolling ticker */}
        <div className="wm2-ticker">
          <div className="wm2-ticker__track">
            {(headlines.length > 0 ? headlines : PLACEHOLDER_HEADLINES).map((h, i) => (
              <span key={i} className="wm2-ticker__item">
                ◆ {h.title}
              </span>
            ))}
            {/* Duplicate for seamless scroll */}
            {(headlines.length > 0 ? headlines : PLACEHOLDER_HEADLINES).map((h, i) => (
              <span key={`dup-${i}`} className="wm2-ticker__item">
                ◆ {h.title}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* ── Section 3: Live Stream + Stats ── */}
      <div className={`wm2-bottom ${flashSection === "stats" ? "wm2-flash" : ""}`}>
        {/* Left: YouTube Live */}
        <div className="wm2-live">
          <div className="wm2-live__header">
            <motion.span
              className="wm2-live__dot"
              animate={{ opacity: [1, 0.2, 1] }}
              transition={{ duration: 1.5, repeat: Infinity }}
            >
              ●
            </motion.span>
            <span className="wm2-live__label">LIVE FEED</span>
          </div>
          <div className="wm2-live__frame-wrapper">
            <iframe
              className="wm2-live__iframe"
              src="https://www.youtube.com/embed/live_stream?channel=UCBi2mrWuNuyYy4gbM6vU7wA&autoplay=1&mute=1"
              title="Bloomberg Live"
              allow="autoplay; encrypted-media"
              allowFullScreen
              frameBorder="0"
            />
          </div>
        </div>

        {/* Right: System Metrics */}
        <div className="wm2-stats">
          <MetricBar label="CPU" value={systemInfo.cpu} />
          <MetricBar label="RAM" value={systemInfo.ram} />
          <MetricBar label="BATTERY" value={systemInfo.battery} />
          <div className="wm2-stats__status">
            <span className="wm2-stats__status-label">STATUS</span>
            <motion.span
              className="wm2-stats__status-value"
              style={{ color: statusColor }}
              animate={
                status === "listening"
                  ? { opacity: [1, 0.4, 1] }
                  : { opacity: 1 }
              }
              transition={
                status === "listening"
                  ? { duration: 1.5, repeat: Infinity, ease: "easeInOut" }
                  : {}
              }
            >
              {statusLabel}
            </motion.span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Placeholder headlines when no data ───────────

const PLACEHOLDER_HEADLINES: NewsHeadline[] = [
  { title: "Awaiting intelligence feed...", source: "SYSTEM", timestamp: "--:--:--" },
  { title: "Global monitoring active", source: "JARVIS", timestamp: "--:--:--" },
  { title: "All systems nominal", source: "CORE", timestamp: "--:--:--" },
  { title: "Standing by for data stream", source: "NET", timestamp: "--:--:--" },
];

// ── Generate map markers from news content ───────

const CONFLICT_KEYWORDS = ["war", "attack", "bomb", "conflict", "military", "strike", "tension", "crisis", "threat", "missile"];
const POSITIVE_KEYWORDS = ["peace", "deal", "agreement", "aid", "rescue", "recovery", "growth", "success", "record"];
const SCIENCE_KEYWORDS = ["space", "nasa", "research", "ai", "tech", "quantum", "launch", "discovery", "climate", "science"];

const CITY_COORDS: Record<string, [number, number]> = {
  "ukraine": [48.38, 31.17], "russia": [55.75, 37.62], "china": [35.86, 104.2],
  "israel": [31.05, 34.85], "iran": [32.43, 53.69], "india": [20.59, 78.96],
  "usa": [37.09, -95.71], "uk": [55.38, -3.44], "france": [46.23, 2.21],
  "germany": [51.17, 10.45], "japan": [36.2, 138.25], "korea": [35.91, 127.77],
  "brazil": [-14.24, -51.93], "australia": [-25.27, 133.78], "taiwan": [23.7, 121.0],
  "gaza": [31.35, 34.31], "syria": [34.8, 38.99], "africa": [8.78, 34.51],
  "europe": [54.53, 15.26], "middle east": [29.31, 47.48],
};

function generateNewsMarkers(headlines: NewsHeadline[]): GeoMarker[] {
  const markers: GeoMarker[] = [];
  let counter = 0;

  for (const h of headlines) {
    const lower = h.title.toLowerCase();
    let markerType: GeoMarker["type"] = "science";

    if (CONFLICT_KEYWORDS.some((kw) => lower.includes(kw))) markerType = "conflict";
    else if (POSITIVE_KEYWORDS.some((kw) => lower.includes(kw))) markerType = "positive";
    else if (SCIENCE_KEYWORDS.some((kw) => lower.includes(kw))) markerType = "science";
    else continue; // skip generic headlines

    // Find a location match
    for (const [place, coords] of Object.entries(CITY_COORDS)) {
      if (lower.includes(place)) {
        markers.push({
          id: `news-${counter++}`,
          lat: coords[0] + (Math.random() - 0.5) * 2,
          lng: coords[1] + (Math.random() - 0.5) * 2,
          label: h.title.substring(0, 60),
          type: markerType,
          pulse: markerType === "conflict",
        });
        break;
      }
    }
  }

  return markers;
}
