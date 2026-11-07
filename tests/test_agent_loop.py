"""End-to-end agent-loop test using a scripted chat model (no real LLM needed)."""
from typing import Any, List

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from src.travel_planner.agent import build_agent, plan_trip


class ScriptedToolModel(BaseChatModel):
    """Emits a fixed sequence of tool calls, then a final answer."""

    script: List[Any] = []
    cursor: int = 0

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        step = self.script[min(self.cursor, len(self.script) - 1)]
        self.cursor += 1
        return ChatResult(generations=[ChatGeneration(message=step)])


def _call(name, args, idx):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"c{idx}"}])


def test_agent_executes_tools_then_answers():
    script = [
        _call("search_flights", {"origin": "Mumbai", "destination": "Goa"}, 1),
        _call("recommend_hotels", {"city": "Goa", "min_stars": 4}, 2),
        _call("plan_daily_schedule", {"city": "Goa", "days": 3}, 3),
        _call("estimate_budget", {"flight_price": 3304, "hotel_price_per_night": 1232, "nights": 2}, 4),
        AIMessage(content="## Trip Summary\nDone."),
    ]
    outcome = plan_trip("3 days Mumbai to Goa", agent=build_agent(ScriptedToolModel(script=script)))
    assert outcome["tools_called"] == ["search_flights", "recommend_hotels",
                                       "plan_daily_schedule", "estimate_budget"]
    assert outcome["answer"].startswith("## Trip Summary")
