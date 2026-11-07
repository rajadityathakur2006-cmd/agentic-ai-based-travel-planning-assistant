"""Places discovery tool: rank attractions in a city by rating and preferred type."""
import json
from typing import Optional

from langchain.tools import tool

from ..database import ensure_database, get_connection


def query_places(city: str, preferred_types: Optional[list] = None, min_rating: float = 0.0) -> list:
    """Return places in ``city`` with rating >= ``min_rating``, best first.

    Places whose type is in ``preferred_types`` are listed before the others.
    """
    ensure_database()
    sql = """
    SELECT p.place_id, p.place_name AS name, c.city_name AS city,
           t.place_type_name AS type, p.rating
    FROM places p
    JOIN cities c ON c.city_id = p.city_id
    JOIN place_types t ON t.place_type_id = p.place_type_id
    WHERE lower(c.city_name) = lower(?) AND p.rating >= ?
    """
    with get_connection() as con:
        rows = [dict(r) for r in con.execute(sql, (city, min_rating))]
    wanted = {t.lower() for t in (preferred_types or [])}
    return sorted(rows, key=lambda r: (r["type"].lower() not in wanted, -r["rating"], r["name"]))


@tool
def discover_places(city: str, preferred_types: str = "", min_rating: float = 0.0) -> str:
    """Find attractions in a city.

    Args:
        city: Destination city.
        preferred_types: Comma-separated types such as "beach,temple,market".
        min_rating: Minimum rating on a 0-5 scale.

    Returns JSON with places ranked by preference match and rating.
    """
    try:
        types = [t.strip() for t in preferred_types.split(",") if t.strip()]
        places = query_places(city.strip(), types, min_rating)
        return json.dumps({"city": city, "count": len(places), "places": places}, ensure_ascii=False)
    except Exception as error:
        return json.dumps({"error": f"Place discovery failed: {error}"})
