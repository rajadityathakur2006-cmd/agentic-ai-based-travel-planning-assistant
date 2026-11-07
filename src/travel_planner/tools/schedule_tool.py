"""Daily schedule tool: spread ranked places over the days of the trip."""
import json

from langchain.tools import tool

from .places_tool import query_places


def allocate_places_to_days(places: list, days: int, per_day: int = 2) -> list:
    """Greedy allocation: highest-rated first, avoiding same-type repeats within a day."""
    remaining = list(places)
    plan = []
    for day in range(1, days + 1):
        chosen = []
        for place in list(remaining):
            if len(chosen) == per_day:
                break
            if all(place["type"] != c["type"] for c in chosen):
                chosen.append(place)
                remaining.remove(place)
        while len(chosen) < per_day and remaining:  # relax the diversity rule if needed
            chosen.append(remaining.pop(0))
        plan.append({"day": day, "places": chosen})
    return plan


@tool
def plan_daily_schedule(city: str, days: int, preferred_types: str = "", per_day: int = 2) -> str:
    """Build a day-wise sightseeing schedule for a city.

    Args:
        city: Destination city.
        days: Number of sightseeing days (1-7).
        preferred_types: Comma-separated preferred place types.
        per_day: Number of attractions per day (default 2).
    """
    try:
        if not 1 <= days <= 7:
            return json.dumps({"error": "days must be between 1 and 7"})
        types = [t.strip() for t in preferred_types.split(",") if t.strip()]
        ranked = query_places(city.strip(), types)
        return json.dumps({"city": city, "schedule": allocate_places_to_days(ranked, days, per_day)},
                          ensure_ascii=False)
    except Exception as error:
        return json.dumps({"error": f"Scheduling failed: {error}"})
