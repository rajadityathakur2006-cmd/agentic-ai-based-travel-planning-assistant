"""Budget estimation tool: flights + hotel + local expenses."""
import json

from langchain.tools import tool

from .. import config


def calculate_budget(flight_price: int, hotel_price_per_night: int, nights: int,
                     travelers: int = 1, rooms: int = 1, return_flight_price: int = 0,
                     daily_local_expense: int = config.DEFAULT_DAILY_LOCAL_EXPENSE) -> dict:
    """Return an itemised cost breakdown in INR.

    Flights are charged per traveller, hotels per room per night, and local food and
    transport per traveller per day (``nights + 1`` days).
    """
    if nights < 1 or travelers < 1 or rooms < 1:
        raise ValueError("nights, travelers and rooms must be at least 1")
    flights = (flight_price + return_flight_price) * travelers
    hotel = hotel_price_per_night * nights * rooms
    local = daily_local_expense * (nights + 1) * travelers
    return {"flights_inr": flights, "hotel_inr": hotel, "food_and_local_travel_inr": local,
            "total_inr": flights + hotel + local, "travelers": travelers, "nights": nights}


@tool
def estimate_budget(flight_price: int, hotel_price_per_night: int, nights: int,
                    travelers: int = 1, rooms: int = 1, return_flight_price: int = 0,
                    daily_local_expense: int = config.DEFAULT_DAILY_LOCAL_EXPENSE) -> str:
    """Estimate total trip cost in INR.

    Args:
        flight_price: One-way flight price per traveller.
        hotel_price_per_night: Price per room per night.
        nights: Number of nights.
        travelers: Number of travellers.
        rooms: Number of rooms.
        return_flight_price: Return flight price per traveller (0 if none).
        daily_local_expense: Food and local transport per person per day.
    """
    try:
        return json.dumps(calculate_budget(flight_price, hotel_price_per_night, nights,
                                           travelers, rooms, return_flight_price, daily_local_expense))
    except ValueError as error:
        return json.dumps({"error": str(error)})
