"""Agent factory and convenience runner."""
import os

from .prompts import SYSTEM_PROMPT
from .tools import ALL_TOOLS

DEFAULT_MODEL = "anthropic:claude-sonnet-4-6"


def build_agent(model=None):
    """Create the tool-calling travel agent.

    ``model`` may be a "provider:model" string or any LangChain chat model object
    (used by the tests to inject a scripted model).
    """
    from langchain.agents import create_agent  # imported lazily to keep CLI start-up fast

    model = model or os.getenv("TRAVEL_LLM_MODEL", DEFAULT_MODEL)
    return create_agent(model=model, tools=ALL_TOOLS, system_prompt=SYSTEM_PROMPT)


def plan_trip(query: str, agent=None) -> dict:
    """Run the agent on a natural-language query.

    Returns the final answer text and the ordered list of tool names that were called.
    """
    agent = agent or build_agent()
    result = agent.invoke({"messages": [{"role": "user", "content": query}]})
    messages = result["messages"]
    tool_calls = [call["name"] for m in messages for call in getattr(m, "tool_calls", []) or []]
    content = messages[-1].content
    if isinstance(content, list):
        content = "".join(block.get("text", "") for block in content if isinstance(block, dict))
    return {"answer": content, "tools_called": tool_calls}
