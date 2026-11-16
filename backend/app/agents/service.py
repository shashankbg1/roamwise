"""Run the agent graph and turn its final state into an Itinerary."""

from app.agents.graph import build_graph
from app.agents.state import Deps, TripState
from app.models.schemas import Itinerary, Place, TripRequest


def _to_itinerary(state: TripState, deps: Deps, base: Itinerary | None = None) -> Itinerary:
    fields = {
        "request": state["request"],
        "location": state["location"],
        "overview": state["overview"],
        "brief": state["brief"],
        "days": state["days"],
        "budget": state["budget"],
        "critique": state["critique"],
        "llm_provider": deps.llm.name,
    }
    if base is not None:
        # A refinement keeps the trip's identity and counts as one more revision.
        return base.model_copy(update={**fields, "revisions": base.revisions + 1})
    return Itinerary(**fields, revisions=state.get("attempts", 1) - 1)


async def plan_trip(request: TripRequest, deps: Deps) -> tuple[Itinerary, list[Place]]:
    """Plan a new trip. Returns the itinerary and the places found, which refinement reuses."""
    state = await build_graph().ainvoke({"request": request}, {"configurable": {"deps": deps}})
    return _to_itinerary(state, deps), state["places"]


async def refine_trip(
    itinerary: Itinerary, places: list[Place], message: str, deps: Deps
) -> Itinerary:
    """Apply a follow-up request to a saved trip without repeating the research."""
    initial: TripState = {
        "request": itinerary.request,
        "location": itinerary.location,
        "weather": [d.weather for d in itinerary.days if d.weather],
        "places": places,
        "brief": itinerary.brief,
        "previous": itinerary.days,
        "feedback": message,
    }
    state = await build_graph().ainvoke(initial, {"configurable": {"deps": deps}})
    return _to_itinerary(state, deps, base=itinerary)
