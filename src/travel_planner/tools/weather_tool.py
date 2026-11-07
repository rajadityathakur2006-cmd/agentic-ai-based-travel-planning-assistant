"""Weather tool backed by the free Open-Meteo API (no key required)."""
import json
from datetime import date, datetime, timedelta

import requests
from langchain.tools import tool

from .. import config

WMO_DESCRIPTIONS = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Rime fog", 51: "Light drizzle", 53: "Drizzle", 55: "Dense drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain", 71: "Light snow", 73: "Snow",
    75: "Heavy snow", 80: "Rain showers", 81: "Rain showers", 82: "Violent showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Severe thunderstorm",
}


def describe_weather_code(code: int) -> str:
    """Translate a WMO weather code into plain English."""
    return WMO_DESCRIPTIONS.get(int(code), "Unknown")


def _select_endpoint(start: date, today: date):
    """Pick forecast, archive or same-dates-last-year (climatology) for a date range.

    Returns ``(url, shift_years, source_label)``.
    """
    horizon = today + timedelta(days=config.FORECAST_HORIZON_DAYS)
    if start < today - timedelta(days=5):
        return config.ARCHIVE_URL, 0, "historical archive"
    if start <= horizon:
        return config.FORECAST_URL, 0, "live forecast"
    return config.ARCHIVE_URL, 1, "climatological estimate (same dates last year)"


def fetch_daily_weather(city: str, start_date: str, end_date: str, today: date = None) -> dict:
    """Fetch daily max/min temperature, rain and conditions for a city and date range."""
    if city not in config.CITY_COORDINATES:
        raise ValueError(f"Unknown city '{city}'. Known: {sorted(config.CITY_COORDINATES)}")
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    if end < start:
        raise ValueError("end_date must not be before start_date")
    today = today or date.today()
    url, shift, label = _select_endpoint(start, today)
    query_start = start.replace(year=start.year - shift) if shift else start
    query_end = end.replace(year=end.year - shift) if shift else end
    latitude, longitude = config.CITY_COORDINATES[city]
    params = {
        "latitude": latitude, "longitude": longitude, "timezone": "auto",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum",
        "start_date": query_start.isoformat(), "end_date": query_end.isoformat(),
    }
    response = requests.get(url, params=params, timeout=config.HTTP_TIMEOUT_SECONDS)
    response.raise_for_status()
    daily = response.json()["daily"]
    days = []
    for index, day in enumerate(daily["time"]):
        shown = (datetime.strptime(day, "%Y-%m-%d").date().replace(year=start.year + 0)
                 if not shift else start + timedelta(days=index))
        days.append({
            "date": shown.isoformat() if shift else day,
            "condition": describe_weather_code(daily["weather_code"][index]),
            "max_temp_c": daily["temperature_2m_max"][index],
            "min_temp_c": daily["temperature_2m_min"][index],
            "rain_mm": daily["precipitation_sum"][index],
        })
    return {"city": city, "source": label, "days": days}


@tool
def get_weather_forecast(city: str, start_date: str, end_date: str) -> str:
    """Get day-by-day weather for a destination.

    Args:
        city: Destination city name.
        start_date: First day of stay, YYYY-MM-DD.
        end_date: Last day of stay, YYYY-MM-DD.

    Returns JSON with condition and temperatures per day, and the data source
    (live forecast, archive, or climatological estimate).
    """
    try:
        return json.dumps(fetch_daily_weather(city.strip(), start_date.strip(), end_date.strip()))
    except requests.RequestException as error:
        return json.dumps({"error": f"Weather service unavailable: {error}",
                           "advice": "Continue the plan and state that weather is unavailable."})
    except (ValueError, KeyError) as error:
        return json.dumps({"error": str(error)})
