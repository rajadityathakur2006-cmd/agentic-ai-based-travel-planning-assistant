"""Command-line entry point: python main.py "3-day trip from Mumbai to Goa on 2025-12-06"."""
import sys

from dotenv import load_dotenv

from src.travel_planner.agent import plan_trip
from src.travel_planner.database import initialise_database


def main() -> None:
    load_dotenv()
    initialise_database()
    query = " ".join(sys.argv[1:]) or input("Describe your trip: ")
    try:
        outcome = plan_trip(query)
    except Exception as error:
        print(f"Could not plan the trip: {error}")
        sys.exit(1)
    print(outcome["answer"])
    print("\nTools used:", " -> ".join(outcome["tools_called"]))


if __name__ == "__main__":
    main()
