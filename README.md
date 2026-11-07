# Agentic AI-Based Travel Planning Assistant (LangChain)

An autonomous travel-planning agent. The user describes a trip in natural language; a
LangChain tool-calling agent decides which tools to call (flights, hotels, places,
live weather, budget), reasons over the results and returns a structured itinerary.

## Features
- Six LangChain tools backed by a normalised SQLite database built from the supplied JSON files
- Live weather from Open-Meteo (no API key), with archive / climatology fallbacks
- Cheapest vs fastest flights, one-stop routing, value-score hotel ranking, diversified day plans
- Streamlit UI with interactive filters, plus a CLI
- 20 automated tests (tools, error handling, scripted end-to-end agent loop)

## Quick start
```bash
git clone <your-repo-url> && cd agentic-travel-planner
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # add your LLM API key
pytest -q                                              # optional: run the tests
streamlit run app.py                                   # web UI
python main.py "3-day trip from Mumbai to Goa on 2025-12-06, love beaches"   # CLI
```

## Project layout
```
app.py  main.py  requirements.txt  .env.example
data/            flights.json  hotels.json  places.json
src/travel_planner/
    config.py  database.py  prompts.py  agent.py
    tools/       flight_tool  hotel_tool  places_tool  weather_tool  budget_tool  schedule_tool
tests/           test_tools.py  test_agent_loop.py
```

## Data notes
The datasets are synthetic: flights are dated 2025 and cover 25 of 56 possible city pairs.
The agent discloses date substitutions and missing routes instead of inventing data.
