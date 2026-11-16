"""The agent workflow as a LangGraph state machine.

    START ──> researcher ──> planner ──> budget ──> critic ──> END
      │                         ▲                      │
      └── (refining) ───────────┘◄──── rejected ───────┘

A new trip starts at the researcher. Refining a saved trip skips research and starts at the
planner. When the critic rejects a draft, the planner tries again, up to `max_revisions` times.
"""

from functools import lru_cache

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.agents import nodes
from app.agents.state import TripState, deps_from


def _entry(state: TripState) -> str:
    return "planner" if state.get("feedback") else "researcher"


def _after_critic(state: TripState, config: RunnableConfig) -> str:
    if state["critique"].approved or state.get("feedback"):
        return END
    revisions_used = state.get("attempts", 1) - 1
    return END if revisions_used >= deps_from(config).max_revisions else "planner"


@lru_cache
def build_graph():
    graph = StateGraph(TripState)
    graph.add_node("researcher", nodes.researcher)
    graph.add_node("planner", nodes.planner)
    graph.add_node("budget", nodes.budget)
    graph.add_node("critic", nodes.critic)

    graph.add_conditional_edges(START, _entry, ["researcher", "planner"])
    graph.add_edge("researcher", "planner")
    graph.add_edge("planner", "budget")
    graph.add_edge("budget", "critic")
    graph.add_conditional_edges("critic", _after_critic, ["planner", END])
    return graph.compile()
