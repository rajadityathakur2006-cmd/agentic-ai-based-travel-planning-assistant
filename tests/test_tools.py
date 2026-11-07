"""Unit tests for the data layer and tools (no network, no LLM)."""
import json
from datetime import date
from unittest import mock

import pytest

from src.travel_planner import config
from src.travel_planner.database import initialise_database
from src.travel_planner.tools import (discover_places, estimate_budget, get_weather_forecast,
                                      plan_daily_schedule, recommend_hotels, search_flights)
from src.travel_planner.tools.budget_tool import calculate_budget
from src.travel_planner.tools.hotel_tool import compute_value_score
from src.travel_planner.tools.schedule_tool import allocate_places_to_days
from src.travel_planner.tools.weather_tool import _select_endpoint, describe_weather_code


@pytest.fixture(scope="session", autouse=True)
def database():
    return initialise_database()


def test_row_counts(database):
    assert (database["flights"], database["hotels"], database["places"]) == (30, 40, 40)
    assert database["hotel_amenities"] == 138


def test_cheapest_and_fastest_direct_flight():
    data = json.loads(search_flights.invoke({"origin": "Bangalore", "destination": "Goa"}))
    assert data["count"] == 2
    assert data["cheapest"]["price_inr"] == 5356
    assert data["fastest"]["duration_minutes"] == 60


def test_city_names_are_case_insensitive():
    assert json.loads(search_flights.invoke({"origin": "mumbai", "destination": "GOA"}))["count"] == 1


def test_exact_and_fallback_date_matching():
    exact = json.loads(search_flights.invoke(
        {"origin": "Mumbai", "destination": "Goa", "travel_date": "2025-07-15"}))
    other = json.loads(search_flights.invoke(
        {"origin": "Mumbai", "destination": "Goa", "travel_date": "2026-02-12"}))
    assert exact["date_match"] == "exact"
    assert other["date_match"] == "route_only" and other["count"] == 1


def test_missing_route_returns_empty_without_error():
    data = json.loads(search_flights.invoke({"origin": "Delhi", "destination": "Goa"}))
    assert data["count"] == 0 and data["one_stop_options"] == []


def test_one_stop_route_is_found_and_flagged():
    data = json.loads(search_flights.invoke({"origin": "Hyderabad", "destination": "Jaipur"}))
    assert data["count"] == 0 and data["one_stop_options"]
    assert data["one_stop_options"][0]["hub"] == "Kolkata"
    assert data["one_stop_options"][0]["layover_validated"] is False


def test_hotel_filters_and_ranking():
    data = json.loads(recommend_hotels.invoke(
        {"city": "Goa", "min_stars": 4, "max_price_per_night": 3000, "required_amenities": "pool"}))
    assert data["count"] >= 1
    assert all(h["stars"] >= 4 and h["price_per_night"] <= 3000 and "pool" in h["amenities"]
               for h in data["top_matches"])
    assert data["top_matches"][0]["name"] == "Royal Heritage"   # 5-star at INR 1,232


def test_hotel_no_match_is_graceful():
    data = json.loads(recommend_hotels.invoke({"city": "Delhi", "min_stars": 5, "max_price_per_night": 1000}))
    assert data["count"] == 0 and data["top_matches"] == []


def test_value_score_bounds():
    assert compute_value_score(5, 1000, 1000, 5000) == 1.0
    assert compute_value_score(1, 5000, 1000, 5000) == 0.12


def test_places_sorted_by_preference_then_rating():
    data = json.loads(discover_places.invoke({"city": "Kolkata", "preferred_types": "market"}))
    assert data["places"][0]["type"] == "market"
    rest = [p["rating"] for p in data["places"][1:]]
    assert rest == sorted(rest, reverse=True)


def test_schedule_has_unique_places_and_requested_days():
    plan = json.loads(plan_daily_schedule.invoke({"city": "Goa", "days": 3}))["schedule"]
    ids = [p["place_id"] for d in plan for p in d["places"]]
    assert len(plan) == 3
    assert len(ids) == len(set(ids)) == 5   # Goa has only five places in the dataset


def test_schedule_rejects_bad_days():
    assert "error" in json.loads(plan_daily_schedule.invoke({"city": "Goa", "days": 12}))


def test_budget_matches_brief_style_example():
    b = calculate_budget(4800, 3200, 2)
    assert b["flights_inr"] == 4800 and b["hotel_inr"] == 6400 and b["food_and_local_travel_inr"] == 4500
    assert b["total_inr"] == 15700


def test_budget_validation_error():
    assert "error" in json.loads(estimate_budget.invoke(
        {"flight_price": 1, "hotel_price_per_night": 1, "nights": 0}))


def test_weather_endpoint_selection():
    today = date(2026, 11, 6)
    assert _select_endpoint(date(2026, 11, 20), today)[2] == "live forecast"
    assert _select_endpoint(date(2026, 1, 1), today)[2] == "historical archive"
    assert _select_endpoint(date(2027, 3, 1), today)[1] == 1


def test_weather_code_mapping():
    assert describe_weather_code(0) == "Clear sky" and describe_weather_code(999) == "Unknown"


def _fake_response():
    resp = mock.Mock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"daily": {
        "time": ["2026-11-10", "2026-11-11"], "weather_code": [0, 3],
        "temperature_2m_max": [31.0, 29.5], "temperature_2m_min": [22.0, 21.0],
        "precipitation_sum": [0.0, 1.2]}}
    return resp


def test_weather_success_with_mocked_api():
    with mock.patch("src.travel_planner.tools.weather_tool.requests.get", return_value=_fake_response()):
        data = json.loads(get_weather_forecast.invoke(
            {"city": "Goa", "start_date": "2026-11-10", "end_date": "2026-11-11"}))
    assert data["days"][0]["condition"] == "Clear sky" and data["days"][1]["max_temp_c"] == 29.5


def test_weather_network_failure_is_reported_not_raised():
    import requests
    with mock.patch("src.travel_planner.tools.weather_tool.requests.get",
                    side_effect=requests.ConnectionError("offline")):
        data = json.loads(get_weather_forecast.invoke(
            {"city": "Goa", "start_date": "2026-11-10", "end_date": "2026-11-11"}))
    assert "error" in data and "advice" in data


def test_weather_unknown_city():
    assert "error" in json.loads(get_weather_forecast.invoke(
        {"city": "Atlantis", "start_date": "2026-11-10", "end_date": "2026-11-11"}))
