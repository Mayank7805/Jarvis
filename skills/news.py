"""
skills/news.py — Real-time News Skill (NewsAPI.org)

Fetches top headlines or searches news articles from the NewsAPI
and returns a concise, voice-friendly summary.

Requires NEWS_API_KEY in the .env file.
API docs: https://newsapi.org/docs
"""

import os
import re

import requests
from dotenv import load_dotenv

# Ensure .env is loaded (may already be loaded by main.py, but safe to call again)
load_dotenv()


# ──────────────────────────────────────────────
#  Constants
# ──────────────────────────────────────────────

DEFAULT_COUNTRY = "in"        # ISO 3166-1 alpha-2 (India)
DEFAULT_CATEGORY = "general"  # business, entertainment, general, health, science, sports, technology
MAX_ARTICLES = 5              # Number of articles to summarize


# ──────────────────────────────────────────────
#  Category Mapping
# ──────────────────────────────────────────────

CATEGORY_KEYWORDS: dict[str, str] = {
    # Technology
    "tech": "technology", "technology": "technology", "gadget": "technology",
    "software": "technology", "ai": "technology", "artificial intelligence": "technology",
    "coding": "technology", "programming": "technology", "computer": "technology",
    # Sports
    "sport": "sports", "sports": "sports", "cricket": "sports", "football": "sports",
    "soccer": "sports", "tennis": "sports", "basketball": "sports", "ipl": "sports",
    "match": "sports", "game": "sports", "fifa": "sports", "olympics": "sports",
    # Business
    "business": "business", "economy": "business", "stock": "business",
    "market": "business", "finance": "business", "trading": "business",
    "sensex": "business", "nifty": "business", "shares": "business",
    # Entertainment
    "entertainment": "entertainment", "movie": "entertainment", "film": "entertainment",
    "bollywood": "entertainment", "hollywood": "entertainment", "music": "entertainment",
    "celebrity": "entertainment", "actor": "entertainment",
    # Health
    "health": "health", "medical": "health", "covid": "health", "disease": "health",
    "hospital": "health", "doctor": "health", "vaccine": "health", "fitness": "health",
    # Science
    "science": "science", "space": "science", "nasa": "science", "research": "science",
    "discovery": "science", "isro": "science", "physics": "science",
}

# Country mapping for natural language
COUNTRY_KEYWORDS: dict[str, str] = {
    "india": "in", "indian": "in",
    "us": "us", "usa": "us", "america": "us", "american": "us", "united states": "us",
    "uk": "gb", "britain": "gb", "british": "gb", "england": "gb", "united kingdom": "gb",
    "australia": "au", "australian": "au",
    "canada": "ca", "canadian": "ca",
    "japan": "jp", "japanese": "jp",
    "china": "cn", "chinese": "cn",
    "germany": "de", "german": "de",
    "france": "fr", "french": "fr",
    "russia": "ru", "russian": "ru",
    "world": "us",  # "world news" defaults to US (broadest English coverage)
}


# ──────────────────────────────────────────────
#  Intent Extraction
# ──────────────────────────────────────────────

def extract_category(text: str) -> str:
    """
    Extract a news category from the user's query.

    Checks against CATEGORY_KEYWORDS (case-insensitive).
    Falls back to DEFAULT_CATEGORY if no match is found.

    Args:
        text: The user's raw speech-to-text transcription.

    Returns:
        NewsAPI category string (e.g. "technology", "sports").
    """
    text_lower = text.lower()

    # Check multi-word keys first
    sorted_keys = sorted(CATEGORY_KEYWORDS.keys(), key=len, reverse=True)
    for keyword in sorted_keys:
        if keyword in text_lower:
            return CATEGORY_KEYWORDS[keyword]

    return DEFAULT_CATEGORY


def extract_country(text: str) -> str:
    """
    Extract a country code from the user's query.

    Args:
        text: The user's raw speech-to-text transcription.

    Returns:
        ISO 3166-1 alpha-2 country code.
    """
    text_lower = text.lower()

    sorted_keys = sorted(COUNTRY_KEYWORDS.keys(), key=len, reverse=True)
    for keyword in sorted_keys:
        if keyword in text_lower:
            return COUNTRY_KEYWORDS[keyword]

    return DEFAULT_COUNTRY


def extract_search_query(text: str) -> str | None:
    """
    Extract a specific search topic from the user's query.

    If the user says something like "news about climate change" or
    "search news for election results", extract the topic.

    Args:
        text: The user's raw speech-to-text transcription.

    Returns:
        The extracted search query, or None if it's a general news request.
    """
    text_lower = text.lower().strip()

    # Patterns like: "news about X", "news on X", "search news for X", "what's happening with X"
    patterns = [
        r"news\s+(?:about|on|regarding|related to)\s+(.+)",
        r"search\s+(?:news|headlines)\s+(?:for|about|on)\s+(.+)",
        r"what(?:'s| is)\s+happening\s+(?:with|in|about)\s+(.+)",
        r"tell\s+me\s+about\s+(.+?)(?:\s+news)?$",
        r"(?:latest|recent|current)\s+(?:news|updates)\s+(?:on|about|regarding)\s+(.+)",
        r"any\s+(?:news|updates)\s+(?:on|about|regarding)\s+(.+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            query = match.group(1).strip()
            # Remove trailing filler words
            query = re.sub(r"\s*(please|thanks|thank you|jarvis)$", "", query).strip()
            if query:
                return query

    return None


# ──────────────────────────────────────────────
#  News Fetch — Top Headlines
# ──────────────────────────────────────────────

def get_top_headlines(
    country: str = DEFAULT_COUNTRY,
    category: str = DEFAULT_CATEGORY,
    max_articles: int = MAX_ARTICLES,
) -> str:
    """
    Fetch top headlines from NewsAPI.

    Args:
        country:      ISO 3166-1 alpha-2 country code.
        category:     NewsAPI category (general, business, tech, etc.).
        max_articles: Maximum number of articles to include.

    Returns:
        A concise, voice-friendly summary of the latest headlines.
    """
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key:
        return "I can't fetch news right now. The NewsAPI key is missing."

    url = (
        f"https://newsapi.org/v2/top-headlines"
        f"?country={country}&category={category}"
        f"&pageSize={max_articles}&apiKey={api_key}"
    )

    try:
        resp = requests.get(url, timeout=8)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.HTTPError as e:
        return f"The news service returned an error: {e}"
    except requests.exceptions.ConnectionError:
        return "I can't reach the news service right now. Please check your internet connection."
    except requests.exceptions.Timeout:
        return "The news service took too long to respond. Try again in a moment."
    except Exception as e:
        return f"Something went wrong fetching the news: {e}"

    articles = data.get("articles", [])
    if not articles:
        return f"I couldn't find any {category} news headlines right now."

    return _format_articles(articles, category)


# ──────────────────────────────────────────────
#  News Fetch — Search (Everything)
# ──────────────────────────────────────────────

def search_news(
    query: str,
    max_articles: int = MAX_ARTICLES,
) -> str:
    """
    Search for news articles matching a query using NewsAPI's 'everything' endpoint.

    Args:
        query:        Search keywords.
        max_articles: Maximum number of articles to include.

    Returns:
        A concise, voice-friendly summary of matching articles.
    """
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key:
        return "I can't search news right now. The NewsAPI key is missing."

    url = (
        f"https://newsapi.org/v2/everything"
        f"?q={requests.utils.quote(query)}&sortBy=publishedAt"
        f"&pageSize={max_articles}&language=en&apiKey={api_key}"
    )

    try:
        resp = requests.get(url, timeout=8)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.HTTPError as e:
        return f"The news service returned an error: {e}"
    except requests.exceptions.ConnectionError:
        return "I can't reach the news service right now. Please check your internet connection."
    except requests.exceptions.Timeout:
        return "The news service took too long to respond. Try again in a moment."
    except Exception as e:
        return f"Something went wrong searching the news: {e}"

    articles = data.get("articles", [])
    if not articles:
        return f"I couldn't find any news articles about '{query}'."

    return _format_articles(articles, topic=query)


# ──────────────────────────────────────────────
#  News Dispatcher (called by the router)
# ──────────────────────────────────────────────

def get_news(text: str) -> str:
    """
    Main entry point for the news skill.

    Analyses the user's query to decide between:
      • Keyword search (if a specific topic is detected)
      • Top headlines by country/category (default)

    Args:
        text: The user's raw speech-to-text transcription.

    Returns:
        A voice-friendly news summary string.
    """
    # Check if the user wants news about a specific topic
    search_query = extract_search_query(text)
    if search_query:
        return search_news(search_query)

    # Otherwise, return top headlines for the detected category and country
    category = extract_category(text)
    country = extract_country(text)
    return get_top_headlines(country=country, category=category)


def get_news_data(text: str) -> tuple[str, list[dict] | None]:
    """
    Return both a voice-friendly news summary AND structured headlines for the World Monitor.

    Returns:
        (voice_reply, headlines) — headlines is a list of {title, source} dicts, or None on error.
    """
    import requests as _requests

    api_key = os.getenv("NEWS_API_KEY")
    if not api_key:
        return ("I can't fetch news right now. The NewsAPI key is missing.", None)

    search_query = extract_search_query(text)

    try:
        if search_query:
            url = (
                f"https://newsapi.org/v2/everything"
                f"?q={_requests.utils.quote(search_query)}&sortBy=publishedAt"
                f"&pageSize={MAX_ARTICLES}&language=en&apiKey={api_key}"
            )
        else:
            category = extract_category(text)
            country = extract_country(text)
            url = (
                f"https://newsapi.org/v2/top-headlines"
                f"?country={country}&category={category}"
                f"&pageSize={MAX_ARTICLES}&apiKey={api_key}"
            )

        resp = _requests.get(url, timeout=8)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return (f"Something went wrong fetching the news: {e}", None)

    articles = data.get("articles", [])
    if not articles:
        voice = get_news(text)
        return (voice, None)

    # Build structured headlines for World Monitor
    headlines = []
    for article in articles:
        title = article.get("title", "Untitled")
        source = article.get("source", {}).get("name", "Unknown")
        if " - " in title:
            title = title.rsplit(" - ", 1)[0]
        headlines.append({"title": title, "source": source})

    # Build voice response
    voice = _format_articles(articles, topic=search_query) if search_query else _format_articles(articles)

    return (voice, headlines)


# ──────────────────────────────────────────────
#  Formatting Helper
# ──────────────────────────────────────────────

def _format_articles(articles: list[dict], category: str = "general", topic: str | None = None) -> str:
    """
    Format a list of NewsAPI articles into a voice-friendly summary.

    Args:
        articles: List of article dicts from NewsAPI.
        category: The category label for the intro line.
        topic:    Optional search topic for the intro line.

    Returns:
        A clean, numbered summary suitable for TTS.
    """
    if topic:
        intro = f"Here are the latest news articles about {topic}."
    else:
        intro = f"Here are today's top {category} headlines."

    lines = [intro]
    for i, article in enumerate(articles, start=1):
        title = article.get("title", "Untitled")
        source = article.get("source", {}).get("name", "Unknown source")
        description = article.get("description", "")

        # Clean up title — NewsAPI sometimes appends " - Source Name" to the title
        if " - " in title:
            title = title.rsplit(" - ", 1)[0]

        # Build the summary line
        line = f"{i}. {title}"
        if description:
            # Keep description short for voice readability
            desc_short = description[:120].rstrip(".")
            line += f" — {desc_short}."
        line += f" (Source: {source})"

        lines.append(line)

    return " ".join(lines)
