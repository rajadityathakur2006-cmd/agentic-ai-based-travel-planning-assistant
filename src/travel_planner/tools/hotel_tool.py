"""Hotel recommendation tool: filter and rank hotels.json records."""
import json
from typing import Optional

from langchain.tools import tool

from ..database import ensure_database, get_connection


def compute_value_score(stars: int, price: int, min_price: int, max_price: int) -> float:
    """Blend quality and affordability into a 0-1 score (60% stars, 40% price)."""
    star_component = stars / 5
    span = max(max_price - min_price, 1)
    price_component = 1 - (price - min_price) / span
    return round(0.6 * star_component + 0.4 * price_component, 3)


def query_hotels(city: str, min_stars: int = 1, max_price_per_night: Optional[int] = None,
                 required_amenities: Optional[list] = None, sort_by: str = "value") -> list:
    """Return hotels in ``city`` matching the filters, ranked by ``sort_by``.

    ``sort_by`` is one of ``value`` (default), ``price`` or ``stars``.
    """
    ensure_database()
    sql = """
    SELECT h.hotel_id, h.hotel_name AS name, c.city_name AS city, h.stars,
           h.price_per_night, GROUP_CONCAT(a.amenity_name) AS amenities
    FROM hotels h
    JOIN cities c ON c.city_id = h.city_id
    LEFT JOIN hotel_amenities ha ON ha.hotel_id = h.hotel_id
    LEFT JOIN amenities a ON a.amenity_id = ha.amenity_id
    WHERE lower(c.city_name) = lower(?) AND h.stars >= ?
    """
    params = [city, min_stars]
    if max_price_per_night is not None:
        sql += " AND h.price_per_night <= ?"
        params.append(max_price_per_night)
    sql += " GROUP BY h.hotel_id"
    with get_connection() as con:
        rows = [dict(r) for r in con.execute(sql, params)]
    for r in rows:
        r["amenities"] = sorted((r["amenities"] or "").split(",")) if r["amenities"] else []
    wanted = {a.lower() for a in (required_amenities or [])}
    rows = [r for r in rows if wanted.issubset(set(r["amenities"]))]
    if rows:
        lo = min(r["price_per_night"] for r in rows)
        hi = max(r["price_per_night"] for r in rows)
        for r in rows:
            r["value_score"] = compute_value_score(r["stars"], r["price_per_night"], lo, hi)
    keys = {
        "value": lambda r: -r["value_score"],
        "price": lambda r: r["price_per_night"],
        "stars": lambda r: (-r["stars"], r["price_per_night"]),
    }
    return sorted(rows, key=keys.get(sort_by, keys["value"]))


@tool
def recommend_hotels(city: str, min_stars: int = 1, max_price_per_night: int = 0,
                     required_amenities: str = "", sort_by: str = "value") -> str:
    """Recommend hotels in a city.

    Args:
        city: Destination city.
        min_stars: Minimum star rating (1-5).
        max_price_per_night: Budget cap in INR per night; 0 means no cap.
        required_amenities: Comma-separated list, e.g. "wifi,pool".
        sort_by: "value" (stars + price blend), "price" or "stars".

    Returns JSON listing the top three matches with a value_score.
    """
    try:
        amenities = [a.strip() for a in required_amenities.split(",") if a.strip()]
        hotels = query_hotels(city.strip(), min_stars, max_price_per_night or None, amenities, sort_by)
        return json.dumps({"city": city, "count": len(hotels), "top_matches": hotels[:3]},
                          ensure_ascii=False)
    except Exception as error:
        return json.dumps({"error": f"Hotel search failed: {error}"})
