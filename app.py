"""Streamlit front end: streamlit run app.py"""
from datetime import date, timedelta

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src.travel_planner.agent import plan_trip
from src.travel_planner.config import CITY_COORDINATES
from src.travel_planner.database import ensure_database
from src.travel_planner.tools.flight_tool import query_direct_flights
from src.travel_planner.tools.hotel_tool import query_hotels
from src.travel_planner.tools.places_tool import query_places

load_dotenv()
ensure_database()
CITIES = sorted(CITY_COORDINATES)
INTERESTS = ["beach", "temple", "museum", "market", "park", "fort", "lake", "monument"]

st.set_page_config(page_title="Agentic Travel Planner", page_icon="✈️", layout="wide")
st.title("✈️ Agentic AI Travel Planning Assistant")

with st.sidebar:
    st.header("Trip details")
    origin = st.selectbox("From", CITIES, index=CITIES.index("Mumbai"))
    destination = st.selectbox("To", CITIES, index=CITIES.index("Goa"))
    start = st.date_input("Start date", date.today() + timedelta(days=14))
    days = st.slider("Days", 3, 7, 3)
    travelers = st.number_input("Travellers", 1, 10, 1)
    min_stars = st.slider("Minimum hotel stars", 1, 5, 3)
    max_hotel = st.number_input("Max hotel price / night (₹, 0 = no cap)", 0, 20000, 0, step=500)
    interests = st.multiselect("Interests", INTERESTS, default=["beach", "market"])
    generate = st.button("Generate itinerary", type="primary", use_container_width=True)

plan_tab, flights_tab, hotels_tab, places_tab = st.tabs(["Itinerary", "Flights", "Hotels", "Places"])

with plan_tab:
    if generate:
        if origin == destination:
            st.warning("Origin and destination must be different.")
        else:
            query = (f"Plan a {days}-day trip from {origin} to {destination} starting {start}. "
                     f"Travellers: {travelers}. Minimum hotel stars: {min_stars}. "
                     f"Hotel budget per night: {max_hotel or 'no limit'}. "
                     f"Interests: {', '.join(interests) or 'any'}.")
            with st.spinner("The agent is searching flights, hotels, weather and places..."):
                try:
                    outcome = plan_trip(query)
                    st.markdown(outcome["answer"])
                    st.caption("Tools called: " + " → ".join(outcome["tools_called"]))
                except Exception as error:
                    st.error(f"Could not generate the itinerary: {error}")
    else:
        st.info("Choose your trip details in the sidebar and press **Generate itinerary**.")

with flights_tab:
    result = query_direct_flights(origin, destination)
    st.dataframe(pd.DataFrame(result["options"]), use_container_width=True) if result["count"] \
        else st.warning("No direct flight in the dataset for this route.")

with hotels_tab:
    hotels = query_hotels(destination, min_stars, max_hotel or None)
    st.dataframe(pd.DataFrame(hotels), use_container_width=True) if hotels \
        else st.warning("No hotel matches the filters.")

with places_tab:
    st.dataframe(pd.DataFrame(query_places(destination, interests)), use_container_width=True)
