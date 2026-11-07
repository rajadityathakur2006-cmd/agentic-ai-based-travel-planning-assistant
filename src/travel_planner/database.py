"""SQLite persistence layer: normalised schema, indexes, loading and queries."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from . import config

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS cities (
    city_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    city_name  TEXT NOT NULL UNIQUE,
    latitude   REAL,
    longitude  REAL
);
CREATE TABLE IF NOT EXISTS airlines (
    airline_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    airline_name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS flights (
    flight_id            TEXT PRIMARY KEY,
    airline_id           INTEGER NOT NULL REFERENCES airlines(airline_id),
    origin_city_id       INTEGER NOT NULL REFERENCES cities(city_id),
    destination_city_id  INTEGER NOT NULL REFERENCES cities(city_id),
    departure_time       TEXT NOT NULL,
    arrival_time         TEXT NOT NULL,
    duration_minutes     INTEGER NOT NULL CHECK (duration_minutes > 0),
    price_inr            INTEGER NOT NULL CHECK (price_inr >= 0)
);
CREATE TABLE IF NOT EXISTS hotels (
    hotel_id         TEXT PRIMARY KEY,
    hotel_name       TEXT NOT NULL,
    city_id          INTEGER NOT NULL REFERENCES cities(city_id),
    stars            INTEGER NOT NULL CHECK (stars BETWEEN 1 AND 5),
    price_per_night  INTEGER NOT NULL CHECK (price_per_night >= 0)
);
CREATE TABLE IF NOT EXISTS amenities (
    amenity_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    amenity_name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS hotel_amenities (
    hotel_id   TEXT    NOT NULL REFERENCES hotels(hotel_id),
    amenity_id INTEGER NOT NULL REFERENCES amenities(amenity_id),
    PRIMARY KEY (hotel_id, amenity_id)
);
CREATE TABLE IF NOT EXISTS place_types (
    place_type_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    place_type_name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS places (
    place_id       TEXT PRIMARY KEY,
    place_name     TEXT NOT NULL,
    city_id        INTEGER NOT NULL REFERENCES cities(city_id),
    place_type_id  INTEGER NOT NULL REFERENCES place_types(place_type_id),
    rating         REAL NOT NULL CHECK (rating BETWEEN 0 AND 5)
);
CREATE INDEX IF NOT EXISTS idx_flights_route  ON flights(origin_city_id, destination_city_id);
CREATE INDEX IF NOT EXISTS idx_flights_price  ON flights(price_inr);
CREATE INDEX IF NOT EXISTS idx_hotels_city    ON hotels(city_id, stars, price_per_night);
CREATE INDEX IF NOT EXISTS idx_places_city    ON places(city_id, rating DESC);
CREATE INDEX IF NOT EXISTS idx_places_type    ON places(place_type_id);
"""


@contextmanager
def get_connection(db_path: Path = config.DATABASE_PATH):
    """Yield a SQLite connection with row access by column name and FK checks on."""
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except sqlite3.Error:
        connection.rollback()
        raise
    finally:
        connection.close()


def _lookup_id(connection, table, id_col, name_col, value):
    """Insert ``value`` into a lookup table if absent and return its primary key."""
    connection.execute(f"INSERT OR IGNORE INTO {table} ({name_col}) VALUES (?)", (value,))
    row = connection.execute(
        f"SELECT {id_col} FROM {table} WHERE {name_col} = ?", (value,)
    ).fetchone()
    return row[0]


def _minutes_between(departure: str, arrival: str) -> int:
    delta = datetime.fromisoformat(arrival) - datetime.fromisoformat(departure)
    return int(delta.total_seconds() // 60)


def initialise_database(db_path: Path = config.DATABASE_PATH, reset: bool = True) -> dict:
    """Create the schema and load the three JSON datasets. Returns row counts."""
    if reset and Path(db_path).exists():
        Path(db_path).unlink()
    try:
        flights = json.loads(config.FLIGHTS_JSON.read_text(encoding="utf-8"))
        hotels = json.loads(config.HOTELS_JSON.read_text(encoding="utf-8"))
        places = json.loads(config.PLACES_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Could not read dataset files: {error}") from error

    with get_connection(db_path) as con:
        con.executescript(SCHEMA_SQL)
        for name, (lat, lon) in config.CITY_COORDINATES.items():
            con.execute(
                "INSERT OR IGNORE INTO cities (city_name, latitude, longitude) VALUES (?,?,?)",
                (name, lat, lon),
            )
        for f in flights:
            con.execute(
                "INSERT INTO flights VALUES (?,?,?,?,?,?,?,?)",
                (
                    f["flight_id"],
                    _lookup_id(con, "airlines", "airline_id", "airline_name", f["airline"]),
                    _lookup_id(con, "cities", "city_id", "city_name", f["from"]),
                    _lookup_id(con, "cities", "city_id", "city_name", f["to"]),
                    f["departure_time"], f["arrival_time"],
                    _minutes_between(f["departure_time"], f["arrival_time"]),
                    f["price"],
                ),
            )
        for h in hotels:
            con.execute(
                "INSERT INTO hotels VALUES (?,?,?,?,?)",
                (h["hotel_id"], h["name"],
                 _lookup_id(con, "cities", "city_id", "city_name", h["city"]),
                 h["stars"], h["price_per_night"]),
            )
            for amenity in h["amenities"]:
                amenity_id = _lookup_id(con, "amenities", "amenity_id", "amenity_name", amenity)
                con.execute("INSERT INTO hotel_amenities VALUES (?,?)", (h["hotel_id"], amenity_id))
        for p in places:
            con.execute(
                "INSERT INTO places VALUES (?,?,?,?,?)",
                (p["place_id"], p["name"],
                 _lookup_id(con, "cities", "city_id", "city_name", p["city"]),
                 _lookup_id(con, "place_types", "place_type_id", "place_type_name", p["type"]),
                 p["rating"]),
            )
        return {
            table: con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("cities", "airlines", "flights", "hotels", "amenities",
                          "hotel_amenities", "place_types", "places")
        }


def ensure_database(db_path: Path = config.DATABASE_PATH) -> None:
    """Build the database on first use."""
    if not Path(db_path).exists():
        initialise_database(db_path)
