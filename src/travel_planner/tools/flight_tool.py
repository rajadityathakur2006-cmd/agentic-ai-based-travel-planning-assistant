"""Flight search tool: direct and one-stop options from flights.json (via SQLite)."""
import json
from typing import Optional

from langchain.tools import tool

from ..database import ensure_database, get_connection

_BASE_QUERY = """
SELECT f.flight_id, a.airline_name AS airline, o.city_name AS origin,
       d.city_name AS destination, f.departure_time, f.arrival_time,
       f.duration_minutes, f.price_inr
FROM flights f
JOIN airlines a ON a.airline_id = f.airline_id
JOIN cities  o ON o.city_id = f.origin_city_id
JOIN cities  d ON d.city_id = f.destination_city_id
"""


def query_direct_flights(origin: str, destination: str, travel_date: Optional[str] = None) -> dict:
    """Return direct flights for a route, optionally restricted to ``YYYY-MM-DD``.

    The bundled dataset covers calendar year 2025 only. If no flight exists on the
    requested date, all flights on the route are returned with ``date_match`` set to
    ``"route_only"`` so the agent can disclose the substitution to the user.
    """
    ensure_database()
    with get_connection() as con:
        rows = [dict(r) for r in con.execute(
            _BASE_QUERY + " WHERE lower(o.city_name)=lower(?) AND lower(d.city_name)=lower(?)"
            " ORDER BY f.price_inr", (origin, destination))]
    date_match = "not_requested"
    if travel_date:
        on_date = [r for r in rows if r["departure_time"].startswith(travel_date)]
        date_match = "exact" if on_date else "route_only"
        rows = on_date or rows
    return {
        "origin": origin, "destination": destination, "date_match": date_match,
        "count": len(rows),
        "cheapest": min(rows, key=lambda r: r["price_inr"]) if rows else None,
        "fastest": min(rows, key=lambda r: (r["duration_minutes"], r["price_inr"])) if rows else None,
        "options": rows[:5],
    }


def query_one_stop_flights(origin: str, destination: str) -> list:
    """Find origin -> hub -> destination itineraries (schedule-template mode).

    Dataset dates are independent, so layover times are not validated; results are
    flagged accordingly and sorted by combined price.
    """
    ensure_database()
    sql = f"""
    SELECT l1.flight_id AS leg1_id, l1.airline AS leg1_airline, l1.origin AS origin,
           l1.destination AS hub, l1.price_inr AS leg1_price, l1.duration_minutes AS leg1_minutes,
           l2.flight_id AS leg2_id, l2.airline AS leg2_airline, l2.destination AS destination,
           l2.price_inr AS leg2_price, l2.duration_minutes AS leg2_minutes
    FROM ({_BASE_QUERY.replace('f.flight_id,', 'f.flight_id AS flight_id,')}) l1
    JOIN ({_BASE_QUERY}) l2 ON l1.destination = l2.origin
    WHERE lower(l1.origin)=lower(?) AND lower(l2.destination)=lower(?)
    """
    # The sub-selects expose column aliases directly, so wrap them in readable names.
    with get_connection() as con:
        rows = [dict(r) for r in con.execute(sql, (origin, destination))]
    for r in rows:
        r["total_price_inr"] = r["leg1_price"] + r["leg2_price"]
        r["total_flight_minutes"] = r["leg1_minutes"] + r["leg2_minutes"]
        r["layover_validated"] = False
    return sorted(rows, key=lambda r: r["total_price_inr"])[:3]


@tool
def search_flights(origin: str, destination: str, travel_date: str = "") -> str:
    """Search flights between two Indian cities.

    Args:
        origin: Departure city, e.g. "Delhi".
        destination: Arrival city, e.g. "Goa".
        travel_date: Optional departure date in YYYY-MM-DD format.

    Returns JSON with the cheapest and fastest direct flights. If there is no direct
    flight, one-stop options are returned instead; an empty result means no
    connection exists in the dataset.
    """
    try:
        result = query_direct_flights(origin.strip(), destination.strip(), travel_date.strip() or None)
        if result["count"] == 0:
            result["one_stop_options"] = query_one_stop_flights(origin.strip(), destination.strip())
            result["message"] = ("No direct flight found." if result["one_stop_options"]
                                 else "No direct or one-stop flight found for this route.")
        return json.dumps(result, ensure_ascii=False)
    except Exception as error:  # surfaced to the LLM so it can recover
        return json.dumps({"error": f"Flight search failed: {error}"})
