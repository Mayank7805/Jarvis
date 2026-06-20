/**
 * screens/WorldDashboard.tsx — Full-Screen World Intelligence Dashboard
 *
 * Voice-triggered overlay (100vw × 100vh) that displays:
 *   • Interactive dark world map with news-location markers
 *   • Top headlines with image cards
 *   • Live market data (NIFTY, SENSEX, BTC) with sparklines
 *   • Sports headlines feed
 *   • Weather widget
 *   • Scrolling ticker bar
 *   • Expandable news detail view with Gemini summaries
 *
 * Activated via WebSocket event "open_dashboard", closed via "close_dashboard".
 */

import React, { useState, useEffect, useCallback, useMemo, useRef, Component } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { MapContainer, TileLayer, CircleMarker, Popup, Tooltip, useMap } from "react-leaflet";

// ── Types ────────────────────────────────────────

interface Article {
  title: string;
  source: string;
  url: string;
  urlToImage: string;
  publishedAt: string;
  description: string;
  category: string;
}

interface MarketItem {
  name: string;
  symbol: string;
  value: number;
  change: number;
  changePercent: number;
  history: number[];
}

interface WeatherData {
  city: string;
  temp: number;
  feels_like: number;
  condition: string;
  humidity: number;
  icon: string;
}

interface WorldData {
  news: Article[];
  sports: Article[];
  markets: Record<string, MarketItem>;
  weather: WeatherData;
  timestamp: string;
}

interface WorldDashboardProps {
  isOpen: boolean;
  expandedIndex: number | null;
  onClose: () => void;
}

// ── Map Error Boundary ───────────────────────────

class DashboardMapErrorBoundary extends Component<
  { children: React.ReactNode },
  { hasError: boolean }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }
  static getDerivedStateFromError() {
    return { hasError: true };
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="wd-map-fallback">
          <span className="wd-map-fallback__label">MAP OFFLINE</span>
        </div>
      );
    }
    return this.props.children;
  }
}

// ── Map Defaults Component ───────────────────────

function DashMapDefaults() {
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

// ── Geo Coordinate Dictionary ────────────────────

const COUNTRY_COORDS: Record<string, [number, number]> = {
  india: [20.59, 78.96], usa: [37.09, -95.71], uk: [55.38, -3.44],
  china: [35.86, 104.2], russia: [55.75, 37.62], japan: [36.2, 138.25],
  france: [46.23, 2.21], germany: [51.17, 10.45], brazil: [-14.24, -51.93],
  australia: [-25.27, 133.78], canada: [56.13, -106.35], israel: [31.05, 34.85],
  iran: [32.43, 53.69], ukraine: [48.38, 31.17], korea: [35.91, 127.77],
  taiwan: [23.7, 121.0], gaza: [31.35, 34.31], syria: [34.8, 38.99],
  pakistan: [30.38, 69.35], afghanistan: [33.94, 67.71], iraq: [33.22, 43.68],
  turkey: [38.96, 35.24], egypt: [26.82, 30.8], saudi: [23.89, 45.08],
  italy: [41.87, 12.57], spain: [40.46, -3.75], mexico: [-23.63, -102.55],
  africa: [8.78, 34.51], europe: [54.53, 15.26], "middle east": [29.31, 47.48],
  "new delhi": [28.61, 77.21], delhi: [28.61, 77.21], mumbai: [19.08, 72.88],
  "new york": [40.71, -74.01], london: [51.51, -0.13], tokyo: [35.68, 139.69],
  beijing: [39.9, 116.4], moscow: [55.76, 37.62], paris: [48.86, 2.35],
  dubai: [25.2, 55.27], singapore: [1.35, 103.82], washington: [38.91, -77.04],
};

const CONFLICT_KW = ["war", "attack", "bomb", "conflict", "military", "strike", "tension", "crisis", "threat", "missile", "killed", "death"];
const BUSINESS_KW = ["market", "stock", "economy", "trade", "gdp", "growth", "deal", "merger", "ipo", "investment", "bank", "finance"];
const SCIENCE_KW = ["space", "nasa", "isro", "research", "ai", "tech", "quantum", "launch", "discovery", "science", "climate"];

function getMarkerType(title: string): "conflict" | "business" | "science" {
  const lower = title.toLowerCase();
  if (CONFLICT_KW.some((kw) => lower.includes(kw))) return "conflict";
  if (BUSINESS_KW.some((kw) => lower.includes(kw))) return "business";
  return "science";
}

const MARKER_COLORS: Record<string, string> = {
  conflict: "#ff3366",
  business: "#00ff88",
  science: "#4488ff",
};

function getMarkerCoords(title: string): [number, number] | null {
  const lower = title.toLowerCase();
  for (const [place, coords] of Object.entries(COUNTRY_COORDS)) {
    if (lower.includes(place)) {
      return [
        coords[0] + (Math.random() - 0.5) * 2,
        coords[1] + (Math.random() - 0.5) * 2,
      ];
    }
  }
  return null;
}

// ── Time Ago Helper ──────────────────────────────

function timeAgo(dateStr: string): string {
  if (!dateStr) return "";
  try {
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  } catch {
    return "";
  }
}

// ── Weather Icon (CSS-based) ─────────────────────

function WeatherIcon({ condition }: { condition: string }) {
  const lower = condition.toLowerCase();
  let icon = "☀";
  if (lower.includes("cloud")) icon = "☁";
  else if (lower.includes("rain") || lower.includes("drizzle")) icon = "🌧";
  else if (lower.includes("thunder") || lower.includes("storm")) icon = "⛈";
  else if (lower.includes("snow")) icon = "❄";
  else if (lower.includes("mist") || lower.includes("fog") || lower.includes("haze")) icon = "🌫";
  else if (lower.includes("clear")) icon = "☀";

  return <span className="wd-weather-icon">{icon}</span>;
}

// ── Sparkline Component ──────────────────────────

function Sparkline({ data, color, width = 80, height = 28 }: {
  data: number[];
  color: string;
  width?: number;
  height?: number;
}) {
  if (!data || data.length < 2) {
    return <svg width={width} height={height} />;
  }

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - ((v - min) / range) * (height - 4) - 2;
    return `${x},${y}`;
  }).join(" ");

  return (
    <svg width={width} height={height} className="wd-sparkline">
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// ── Header Clock ─────────────────────────────────

function DashboardClock() {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const time = now.toLocaleTimeString("en-IN", { hour12: false, hour: "2-digit", minute: "2-digit" });
  return <span className="wd-header__clock">{time} IST</span>;
}

// ── News Card Component ──────────────────────────

function NewsCard({
  article,
  index,
  onExpand,
}: {
  article: Article;
  index: number;
  onExpand: (idx: number) => void;
}) {
  return (
    <motion.div
      className="wd-card"
      initial={{ opacity: 0, y: 30, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ delay: 0.15 + index * 0.12, duration: 0.5, ease: "easeOut" }}
      onClick={() => onExpand(index)}
      role="button"
      tabIndex={0}
      id={`wd-card-${index}`}
    >
      {article.urlToImage && (
        <div
          className="wd-card__image"
          style={{ backgroundImage: `url(${article.urlToImage})` }}
        />
      )}
      <div className="wd-card__overlay" />
      <div className="wd-card__content">
        <span className="wd-card__source">{article.source}</span>
        <h3 className="wd-card__title">{article.title}</h3>
        <span className="wd-card__time">{timeAgo(article.publishedAt)}</span>
      </div>
      <span className="wd-card__category">{article.category || "general"}</span>
    </motion.div>
  );
}

// ── Expanded News View ───────────────────────────

function ExpandedNews({
  article,
  onClose,
}: {
  article: Article;
  onClose: () => void;
}) {
  const [summary, setSummary] = useState<string>(article.description || "Loading summary...");

  // Attempt async Gemini summary
  useEffect(() => {
    if (!article.url) return;
    let cancelled = false;
    fetch(`http://localhost:8765/command`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: `summarize this news article in 2 sentences: ${article.url}` }),
    }).catch(() => {/* non-critical */});

    // For now, use the description from NewsAPI
    if (article.description && !cancelled) {
      setSummary(article.description);
    }
    return () => { cancelled = true; };
  }, [article.url, article.description]);

  return (
    <motion.div
      className="wd-expanded"
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.9 }}
      transition={{ duration: 0.35 }}
    >
      <div className="wd-expanded__backdrop" onClick={onClose} />
      <div className="wd-expanded__card">
        {article.urlToImage && (
          <img
            className="wd-expanded__image"
            src={article.urlToImage}
            alt={article.title}
          />
        )}
        <div className="wd-expanded__body">
          <span className="wd-expanded__source">{article.source}</span>
          <h2 className="wd-expanded__title">{article.title}</h2>
          <p className="wd-expanded__summary">{summary}</p>
          <div className="wd-expanded__footer">
            <a
              className="wd-expanded__link"
              href={article.url}
              target="_blank"
              rel="noopener noreferrer"
            >
              Read Full Article →
            </a>
            <span className="wd-expanded__time">{timeAgo(article.publishedAt)}</span>
          </div>
          <button className="wd-expanded__close" onClick={onClose}>
            ✕ CLOSE
          </button>
        </div>
      </div>
    </motion.div>
  );
}

// ── Market Row Component ─────────────────────────

function MarketRow({ market }: { market: MarketItem }) {
  const isPositive = market.changePercent >= 0;
  const color = isPositive ? "#00ff88" : "#ff3366";
  const arrow = isPositive ? "▲" : "▼";

  // Format value
  const formattedValue = market.name === "BTC"
    ? `$${market.value.toLocaleString("en-US", { maximumFractionDigits: 0 })}`
    : market.value.toLocaleString("en-IN", { maximumFractionDigits: 0 });

  return (
    <div className="wd-market-row">
      <div className="wd-market-row__info">
        <span className="wd-market-row__name">{market.name}</span>
        <span className="wd-market-row__value">{formattedValue}</span>
      </div>
      <div className="wd-market-row__change" style={{ color }}>
        <span>{arrow} {Math.abs(market.changePercent).toFixed(2)}%</span>
      </div>
      <Sparkline data={market.history} color={color} />
    </div>
  );
}

// ══════════════════════════════════════════════════
//  MAIN DASHBOARD COMPONENT
// ══════════════════════════════════════════════════

export function WorldDashboard({ isOpen, expandedIndex, onClose }: WorldDashboardProps) {
  const [data, setData] = useState<WorldData | null>(null);
  const [loading, setLoading] = useState(true);
  const [localExpanded, setLocalExpanded] = useState<number | null>(null);
  const refreshTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const marketTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Sync expanded index from voice commands
  useEffect(() => {
    if (expandedIndex !== null) {
      setLocalExpanded(expandedIndex);
    }
  }, [expandedIndex]);

  // Fetch world data
  const fetchData = useCallback(async () => {
    try {
      const resp = await fetch("http://localhost:8765/world-data");
      if (resp.ok) {
        const json: WorldData = await resp.json();
        setData(json);
        setLoading(false);
      }
    } catch (e) {
      console.error("[WorldDashboard] Fetch error:", e);
    }
  }, []);

  // Initial fetch + auto-refresh
  useEffect(() => {
    if (!isOpen) return;

    fetchData();

    // News refresh every 5 minutes
    refreshTimerRef.current = setInterval(fetchData, 5 * 60 * 1000);

    return () => {
      if (refreshTimerRef.current) clearInterval(refreshTimerRef.current);
    };
  }, [isOpen, fetchData]);

  // Market refresh every 60 seconds (lighter endpoint)
  useEffect(() => {
    if (!isOpen) return;

    marketTimerRef.current = setInterval(async () => {
      try {
        const resp = await fetch("http://localhost:8765/world-data");
        if (resp.ok) {
          const json: WorldData = await resp.json();
          setData((prev) => prev ? { ...prev, markets: json.markets } : json);
        }
      } catch (e) {
        // silent
      }
    }, 60 * 1000);

    return () => {
      if (marketTimerRef.current) clearInterval(marketTimerRef.current);
    };
  }, [isOpen]);

  // Keyboard close (Escape)
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (localExpanded !== null) {
          setLocalExpanded(null);
        } else {
          onClose();
        }
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isOpen, localExpanded, onClose]);

  // Generate map markers from news
  const markers = useMemo(() => {
    if (!data?.news) return [];
    return data.news
      .map((article, i) => {
        const coords = getMarkerCoords(article.title);
        if (!coords) return null;
        const type = getMarkerType(article.title);
        return {
          id: `news-${i}`,
          lat: coords[0],
          lng: coords[1],
          title: article.title,
          type,
          color: MARKER_COLORS[type],
        };
      })
      .filter(Boolean) as Array<{
        id: string; lat: number; lng: number;
        title: string; type: string; color: string;
      }>;
  }, [data?.news]);

  if (!isOpen) return null;

  const news = data?.news || [];
  const sports = data?.sports || [];
  const markets = data?.markets || {};
  const weather = data?.weather;

  return (
    <AnimatePresence>
      <motion.div
        className="wd-overlay"
        initial={{ opacity: 0, scale: 0.97 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.97 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
        id="world-dashboard"
      >
        {/* Scanline overlay */}
        <div className="wd-scanline" />

        {/* ── Header ── */}
        <header className="wd-header">
          <div className="wd-header__left">
            <span className="wd-header__diamond">◆</span>
            <span className="wd-header__title">W O R L D &nbsp; I N T E L L I G E N C E</span>
          </div>
          <div className="wd-header__right">
            {weather && (
              <div className="wd-header__weather">
                <WeatherIcon condition={weather.condition} />
                <span className="wd-header__weather-city">{weather.city}</span>
                <span className="wd-header__weather-temp">{weather.temp}°C</span>
              </div>
            )}
            <DashboardClock />
            <button className="wd-header__close" onClick={onClose} title="Close Dashboard">
              ✕
            </button>
          </div>
        </header>

        {/* ── Main Grid ── */}
        <div className="wd-main">
          {/* Left Column: World Map */}
          <div className="wd-map-section">
            <DashboardMapErrorBoundary>
              <MapContainer
                center={[20, 30]}
                zoom={2}
                className="wd-map__container"
                zoomControl={false}
                attributionControl={false}
                scrollWheelZoom={true}
                dragging={true}
                doubleClickZoom={false}
                minZoom={2}
                maxZoom={6}
                style={{ width: "100%", height: "100%", background: "#0a0a0f" }}
              >
                <DashMapDefaults />
                <TileLayer
                  url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
                  attribution=""
                />
                {markers.map((m) => (
                  <CircleMarker
                    key={m.id}
                    center={[m.lat, m.lng]}
                    radius={6}
                    pathOptions={{
                      color: m.color,
                      fillColor: m.color,
                      fillOpacity: 0.6,
                      weight: 2,
                      opacity: 0.8,
                      className: m.type === "conflict" ? "wd-marker-pulse" : "",
                    }}
                  >
                    <Tooltip
                      className="wd-map-tooltip"
                      direction="top"
                      offset={[0, -8]}
                      opacity={0.95}
                    >
                      <span>{m.title.substring(0, 80)}</span>
                    </Tooltip>
                  </CircleMarker>
                ))}
              </MapContainer>
            </DashboardMapErrorBoundary>
            <div className="wd-map__label">GLOBAL INTELLIGENCE OVERLAY</div>

            {/* Map legend */}
            <div className="wd-map__legend">
              <span className="wd-map__legend-item">
                <span className="wd-map__legend-dot" style={{ background: "#ff3366" }} />
                CONFLICT
              </span>
              <span className="wd-map__legend-item">
                <span className="wd-map__legend-dot" style={{ background: "#00ff88" }} />
                ECONOMY
              </span>
              <span className="wd-map__legend-item">
                <span className="wd-map__legend-dot" style={{ background: "#4488ff" }} />
                SCIENCE
              </span>
            </div>
          </div>

          {/* Right Column */}
          <div className="wd-right">
            {/* Top Headlines */}
            <div className="wd-headlines">
              <div className="wd-section-header">
                <span className="wd-section-label">◆ TOP HEADLINES</span>
                <span className="wd-section-count">{news.length} STORIES</span>
              </div>
              <div className="wd-cards-row">
                {loading ? (
                  <div className="wd-loading">
                    <motion.span
                      animate={{ opacity: [0.3, 1, 0.3] }}
                      transition={{ duration: 1.5, repeat: Infinity }}
                    >
                      LOADING INTELLIGENCE...
                    </motion.span>
                  </div>
                ) : (
                  news.slice(0, 3).map((article, i) => (
                    <NewsCard
                      key={`${article.title}-${i}`}
                      article={article}
                      index={i}
                      onExpand={setLocalExpanded}
                    />
                  ))
                )}
              </div>
            </div>

            {/* Bottom Row: Markets + Sports */}
            <div className="wd-bottom-row">
              {/* Markets */}
              <div className="wd-markets">
                <div className="wd-section-header">
                  <span className="wd-section-label">◆ MARKETS</span>
                  <motion.span
                    className="wd-live-dot"
                    animate={{ opacity: [1, 0.2, 1] }}
                    transition={{ duration: 1.5, repeat: Infinity }}
                  >
                    ● LIVE
                  </motion.span>
                </div>
                <div className="wd-markets__list">
                  {["nifty", "sensex", "btc"].map((key) => {
                    const m = markets[key];
                    return m ? (
                      <MarketRow key={key} market={m} />
                    ) : null;
                  })}
                </div>
              </div>

              {/* Sports */}
              <div className="wd-sports">
                <div className="wd-section-header">
                  <span className="wd-section-label">◆ SPORTS</span>
                  <span className="wd-section-count">{sports.length} ITEMS</span>
                </div>
                <div className="wd-sports__list">
                  {sports.slice(0, 4).map((article, i) => (
                    <motion.div
                      key={`sport-${i}`}
                      className="wd-sports__item"
                      initial={{ opacity: 0, x: 20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: 0.3 + i * 0.1 }}
                    >
                      <span className="wd-sports__source">{article.source}</span>
                      <span className="wd-sports__title">{article.title}</span>
                    </motion.div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* ── Ticker Bar ── */}
        <div className="wd-ticker">
          <div className="wd-ticker__track">
            {[...news, ...sports].map((a, i) => (
              <span key={i} className="wd-ticker__item">◆ {a.title}</span>
            ))}
            {/* Duplicate for seamless loop */}
            {[...news, ...sports].map((a, i) => (
              <span key={`dup-${i}`} className="wd-ticker__item">◆ {a.title}</span>
            ))}
          </div>
        </div>

        {/* ── Expanded News Overlay ── */}
        <AnimatePresence>
          {localExpanded !== null && news[localExpanded] && (
            <ExpandedNews
              article={news[localExpanded]}
              onClose={() => setLocalExpanded(null)}
            />
          )}
        </AnimatePresence>
      </motion.div>
    </AnimatePresence>
  );
}
