"""
skills/weather.py — Real-time Weather Skill (OpenWeatherMap)

Fetches current weather data from the OpenWeatherMap API and returns
a concise, voice-friendly summary.

Requires OPENWEATHER_API_KEY in the .env file.
"""

import os

import requests
from dotenv import load_dotenv

# Ensure .env is loaded (may already be loaded by main.py, but safe to call again)
load_dotenv()


# ──────────────────────────────────────────────
#  Major Indian Cities (for city extraction)
# ──────────────────────────────────────────────

KNOWN_CITIES: list[str] = [
    "Delhi", "New Delhi", "Mumbai", "Bangalore", "Bengaluru",
    "Hyderabad", "Chennai", "Kolkata", "Pune", "Ahmedabad",
    "Jaipur", "Lucknow", "Kanpur", "Nagpur", "Indore",
    "Thane", "Bhopal", "Visakhapatnam", "Patna", "Vadodara",
    "Ghaziabad", "Ludhiana", "Agra", "Nashik", "Faridabad",
    "Meerut", "Rajkot", "Varanasi", "Srinagar", "Chandigarh",
    "Coimbatore", "Guwahati", "Noida", "Gurgaon", "Gurugram",
    "Kochi", "Trivandrum", "Thiruvananthapuram", "Mangalore",
    "Dehradun", "Shimla", "Amritsar", "Ranchi", "Raipur",
    # International cities (common asks)
    "London", "New York", "Tokyo", "Dubai", "Singapore",
    "Paris", "Berlin", "Sydney", "Toronto", "San Francisco",
    "Los Angeles", "Chicago", "Seattle", "Boston", "Bangkok",
]

DEFAULT_CITY = "Delhi"


# ──────────────────────────────────────────────
#  City Extraction
# ──────────────────────────────────────────────

def extract_city(text: str) -> str:
    """
    Attempt to extract a city name from the user's query.

    Checks against a list of known cities (case-insensitive).
    Falls back to DEFAULT_CITY if no match is found.

    Args:
        text: The user's raw speech-to-text transcription.

    Returns:
        Matched city name, or "Delhi" as default.
    """
    text_lower = text.lower()

    # Check multi-word cities first (longest match wins)
    sorted_cities = sorted(KNOWN_CITIES, key=len, reverse=True)
    for city in sorted_cities:
        if city.lower() in text_lower:
            return city

    return DEFAULT_CITY


# ──────────────────────────────────────────────
#  Weather Fetch
# ──────────────────────────────────────────────

def get_weather(city: str = DEFAULT_CITY) -> str:
    """
    Fetch current weather for the given city from OpenWeatherMap.

    Args:
        city: City name (e.g. "Mumbai", "London").

    Returns:
        A concise, voice-friendly weather summary string.
    """
    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        return "I can't check the weather right now. The OpenWeatherMap API key is missing."

    url = (
        f"https://api.openweathermap.org/data/2.5/weather"
        f"?q={city}&appid={api_key}&units=metric"
    )

    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.HTTPError:
        return f"I couldn't find weather data for {city}. Please check the city name."
    except requests.exceptions.ConnectionError:
        return "I can't reach the weather service right now. Please check your internet connection."
    except requests.exceptions.Timeout:
        return "The weather service took too long to respond. Try again in a moment."
    except Exception as e:
        return f"Something went wrong fetching the weather: {e}"

    # Parse response
    try:
        temp = round(data["main"]["temp"])
        feels_like = round(data["main"]["feels_like"])
        humidity = data["main"]["humidity"]
        description = data["weather"][0]["description"]
        city_name = data["name"]
    except (KeyError, IndexError):
        return "I got a response from the weather service but couldn't read it properly."

    return (
        f"{city_name} is currently {temp}°C, feels like {feels_like}°C, "
        f"{description}. Humidity is {humidity}%."
    )


def get_weather_data(city: str = DEFAULT_CITY) -> tuple[str, dict | None]:
    """
    Fetch current weather and return BOTH a voice string AND structured data.

    Returns:
        (voice_reply, data_dict) — data_dict is None on error.
        data_dict keys: city, temp, feels_like, condition, humidity.
    """
    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        return ("I can't check the weather right now. The OpenWeatherMap API key is missing.", None)

    url = (
        f"https://api.openweathermap.org/data/2.5/weather"
        f"?q={city}&appid={api_key}&units=metric"
    )

    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.HTTPError:
        return (f"I couldn't find weather data for {city}. Please check the city name.", None)
    except requests.exceptions.ConnectionError:
        return ("I can't reach the weather service right now. Please check your internet connection.", None)
    except requests.exceptions.Timeout:
        return ("The weather service took too long to respond. Try again in a moment.", None)
    except Exception as e:
        return (f"Something went wrong fetching the weather: {e}", None)

    try:
        temp = round(data["main"]["temp"])
        feels_like = round(data["main"]["feels_like"])
        humidity = data["main"]["humidity"]
        description = data["weather"][0]["description"]
        city_name = data["name"]
    except (KeyError, IndexError):
        return ("I got a response from the weather service but couldn't read it properly.", None)

    voice = (
        f"{city_name} is currently {temp}°C, feels like {feels_like}°C, "
        f"{description}. Humidity is {humidity}%."
    )

    structured = {
        "city": city_name,
        "temp": temp,
        "feels_like": feels_like,
        "condition": description,
        "humidity": humidity,
    }

    return (voice, structured)
