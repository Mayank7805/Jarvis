"""
skills/world_briefing.py — World Intelligence Dashboard Data

Fetches and aggregates data for the full-screen World Dashboard:
    • Top headlines (NewsAPI — general + with images)
    • Sports headlines (NewsAPI — category=sports)
    • Market data (Yahoo Finance — NIFTY, SENSEX, BTC)
    • Weather data (OpenWeatherMap — Delhi)

All data is cached for 5 minutes to respect API rate limits.
This module is NOT a BaseSkill subclass — it's called directly
by the router and the /world-data REST endpoint.
"""

import os
import time
import logging
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
#  Cache Configuration
# ──────────────────────────────────────────────

_cache: dict = {}
_cache_timestamps: dict[str, float] = {}

NEWS_CACHE_TTL = 300       # 5 minutes
MARKETS_CACHE_TTL = 60     # 1 minute
WEATHER_CACHE_TTL = 1800   # 30 minutes
SPORTS_CACHE_TTL = 300     # 5 minutes


def _get_cached(key: str, ttl: float):
    """Return cached value if still fresh, else None."""
    if key in _cache and key in _cache_timestamps:
        if (time.time() - _cache_timestamps[key]) < ttl:
            return _cache[key]
    return None


def _set_cached(key: str, value):
    """Store a value in the cache with current timestamp."""
    _cache[key] = value
    _cache_timestamps[key] = time.time()


# ──────────────────────────────────────────────
#  News Fetcher (Top Headlines)
# ──────────────────────────────────────────────

def _fetch_news(category: str = "general", country: str = "us", count: int = 10) -> list[dict]:
    """
    Fetch top headlines from NewsAPI with full article data.

    Falls back to country='us' if primary country returns 0 results.
    Returns list of dicts with: title, source, url, urlToImage,
    publishedAt, description, category.
    """
    cache_key = f"news_{category}_{country}"
    cached = _get_cached(cache_key, NEWS_CACHE_TTL)
    if cached is not None:
        return cached

    api_key = os.getenv("NEWS_API_KEY")
    if not api_key:
        logger.warning("NEWS_API_KEY not set")
        return []

    def _do_fetch(ctry: str) -> list[dict]:
        url = (
            f"https://newsapi.org/v2/top-headlines"
            f"?country={ctry}&category={category}"
            f"&pageSize={count}&apiKey={api_key}"
        )
        try:
            resp = requests.get(url, timeout=8)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"News fetch failed ({category}, {ctry}): {e}")
            return []

        articles = []
        for article in data.get("articles", []):
            title = article.get("title", "")
            if not title or title == "[Removed]":
                continue
            if " - " in title:
                title = title.rsplit(" - ", 1)[0]
            articles.append({
                "title": title,
                "source": article.get("source", {}).get("name", "Unknown"),
                "url": article.get("url", ""),
                "urlToImage": article.get("urlToImage", ""),
                "publishedAt": article.get("publishedAt", ""),
                "description": article.get("description", ""),
                "category": category,
            })
        return articles

    # Try primary country first
    articles = _do_fetch(country)

    # Fallback to US if primary returns empty (free tier limitation)
    if not articles and country != "us":
        logger.info(f"News empty for country={country}, falling back to US")
        articles = _do_fetch("us")

    if articles:
        _set_cached(cache_key, articles)
    return articles


# ──────────────────────────────────────────────
#  Market Data Fetcher (Yahoo Finance)
# ──────────────────────────────────────────────

MARKET_SYMBOLS = {
    "nifty": "^NSEI",
    "sensex": "^BSESN",
    "btc": "BTC-USD",
}


def _fetch_single_market(name: str, symbol: str) -> dict:
    """
    Fetch market data for a single symbol from Yahoo Finance.

    Returns dict with: name, symbol, value, change, changePercent, history.
    """
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        f"?range=1d&interval=15m"
    )

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        resp = requests.get(url, headers=headers, timeout=5)
        resp.raise_for_status()
        data = resp.json()

        result = data.get("chart", {}).get("result", [{}])[0]
        meta = result.get("meta", {})
        indicators = result.get("indicators", {}).get("quote", [{}])[0]

        current = meta.get("regularMarketPrice", 0)
        previous_close = meta.get("chartPreviousClose", meta.get("previousClose", current))

        change = round(current - previous_close, 2)
        change_pct = round((change / previous_close * 100) if previous_close else 0, 2)

        # Extract close prices for sparkline
        closes = indicators.get("close", [])
        history = [round(c, 2) for c in closes if c is not None][-20:]  # last 20 points

        return {
            "name": name.upper(),
            "symbol": symbol,
            "value": round(current, 2),
            "change": change,
            "changePercent": change_pct,
            "history": history,
        }

    except Exception as e:
        logger.error(f"Market fetch failed for {symbol}: {e}")
        return {
            "name": name.upper(),
            "symbol": symbol,
            "value": 0,
            "change": 0,
            "changePercent": 0,
            "history": [],
        }


def _fetch_markets() -> dict:
    """
    Fetch all market data (NIFTY, SENSEX, BTC).

    Returns dict keyed by market name.
    """
    cached = _get_cached("markets", MARKETS_CACHE_TTL)
    if cached is not None:
        return cached

    markets = {}
    for name, symbol in MARKET_SYMBOLS.items():
        markets[name] = _fetch_single_market(name, symbol)

    _set_cached("markets", markets)
    return markets


# ──────────────────────────────────────────────
#  Weather Fetcher
# ──────────────────────────────────────────────

def _fetch_weather(city: str = "Delhi") -> dict:
    """
    Fetch current weather from OpenWeatherMap.

    Returns dict with: city, temp, feels_like, condition, humidity, icon.
    """
    cached = _get_cached(f"weather_{city}", WEATHER_CACHE_TTL)
    if cached is not None:
        return cached

    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        logger.warning("OPENWEATHER_API_KEY not set")
        return {"city": city, "temp": 0, "feels_like": 0, "condition": "unavailable", "humidity": 0, "icon": "01d"}

    url = (
        f"https://api.openweathermap.org/data/2.5/weather"
        f"?q={city}&appid={api_key}&units=metric"
    )

    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()

        result = {
            "city": data.get("name", city),
            "temp": round(data["main"]["temp"]),
            "feels_like": round(data["main"]["feels_like"]),
            "condition": data["weather"][0]["description"],
            "humidity": data["main"]["humidity"],
            "icon": data["weather"][0].get("icon", "01d"),
        }

        _set_cached(f"weather_{city}", result)
        return result

    except Exception as e:
        logger.error(f"Weather fetch failed: {e}")
        return _get_cached(f"weather_{city}", float("inf")) or {
            "city": city, "temp": 0, "feels_like": 0,
            "condition": "unavailable", "humidity": 0, "icon": "01d",
        }


# ──────────────────────────────────────────────
#  Combined Data (for /world-data endpoint)
# ──────────────────────────────────────────────

def get_world_data() -> dict:
    """
    Fetch and return all world dashboard data as a single dict.

    Uses ThreadPoolExecutor to fetch news, sports, markets, and weather
    in parallel for faster response times.

    Returns:
        {news, sports, markets, weather}
    """
    results = {}

    def fetch_news():
        return ("news", _fetch_news(category="general", count=10))

    def fetch_sports():
        return ("sports", _fetch_news(category="sports", count=5))

    def fetch_markets_data():
        return ("markets", _fetch_markets())

    def fetch_weather_data():
        return ("weather", _fetch_weather("Delhi"))

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(fetch_news),
            executor.submit(fetch_sports),
            executor.submit(fetch_markets_data),
            executor.submit(fetch_weather_data),
        ]
        for future in as_completed(futures, timeout=15):
            try:
                key, value = future.result()
                results[key] = value
            except Exception as e:
                logger.error(f"Parallel fetch error: {e}")

    return {
        "news": results.get("news", []),
        "sports": results.get("sports", []),
        "markets": results.get("markets", {}),
        "weather": results.get("weather", {"city": "Delhi", "temp": 0, "feels_like": 0, "condition": "unavailable", "humidity": 0, "icon": "01d"}),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ──────────────────────────────────────────────
#  Spoken Summary (for TTS)
# ──────────────────────────────────────────────

def get_spoken_summary() -> str:
    """
    Generate a concise, TTS-friendly summary of world events.

    Called by the router when the user says "what's happening in the world".
    Jarvis speaks this while the dashboard opens on screen.

    Returns:
        A voice-friendly summary string.
    """
    data = get_world_data()

    parts = ["Here's what's happening in the world."]

    # Top headlines (first 3)
    news = data.get("news", [])
    if news:
        parts.append("Top headlines:")
        for i, article in enumerate(news[:3], 1):
            parts.append(f"{i}. {article['title']}.")

    # Markets
    markets = data.get("markets", {})
    market_parts = []
    for key in ("nifty", "sensex", "btc"):
        m = markets.get(key, {})
        if m.get("value"):
            direction = "up" if m["changePercent"] >= 0 else "down"
            if key == "btc":
                market_parts.append(
                    f"Bitcoin is at ${m['value']:,.0f}, {direction} {abs(m['changePercent'])}%"
                )
            else:
                market_parts.append(
                    f"{m['name']} is at {m['value']:,.0f}, {direction} {abs(m['changePercent'])}%"
                )

    if market_parts:
        parts.append("Markets: " + ". ".join(market_parts) + ".")

    # Weather
    weather = data.get("weather", {})
    if weather.get("temp"):
        parts.append(
            f"Weather in {weather['city']}: {weather['temp']}°C, {weather['condition']}."
        )

    # Sports (first 2)
    sports = data.get("sports", [])
    if sports:
        parts.append("In sports:")
        for article in sports[:2]:
            parts.append(f"{article['title']}.")

    return " ".join(parts)
