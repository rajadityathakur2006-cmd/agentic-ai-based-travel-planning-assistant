"""Central configuration: file paths, city coordinates and cost assumptions."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DATABASE_PATH = PROJECT_ROOT / "travel.db"

FLIGHTS_JSON = DATA_DIR / "flights.json"
HOTELS_JSON = DATA_DIR / "hotels.json"
PLACES_JSON = DATA_DIR / "places.json"

# Latitude / longitude used for weather look-ups (the datasets hold no coordinates).
CITY_COORDINATES = {
    "Delhi": (28.6139, 77.2090),
    "Mumbai": (19.0760, 72.8777),
    "Goa": (15.2993, 74.1240),
    "Bangalore": (12.9716, 77.5946),
    "Chennai": (13.0827, 80.2707),
    "Hyderabad": (17.3850, 78.4867),
    "Kolkata": (22.5726, 88.3639),
    "Jaipur": (26.9124, 75.7873),
}

# Open-Meteo endpoints (no API key required).
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_HORIZON_DAYS = 16
HTTP_TIMEOUT_SECONDS = 10

# Budget assumptions (INR per person per day) for food and local transport.
DEFAULT_DAILY_LOCAL_EXPENSE = 1500
