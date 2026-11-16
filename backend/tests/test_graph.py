"""End-to-end tests of the agent graph with the mock model and faked network calls."""

import httpx
import pytest

from app.agents import nodes
from app.agents.service import plan_trip, refine_trip
from app.agents.state import Deps, TripError
from app.llm.mock import MockProvider
from app.models.schemas import AgentEvent


@pytest.fixture
def deps(monkeypatch, location, places, weather):
    """Deps whose tools return fixture data, plus a list that records emitted events."""

    async def fake_geocode(client, name):
        return None if name == "Nowhereville" else location

    async def fake_weather(client, loc, start, end):
        return weather

    async def fake_places(client, loc, interests):
        return list(places)

    monkeypatch.setattr(nodes, "geocode", fake_geocode)
    monkeypatch.setattr(nodes, "get_weather", fake_weather)
    monkeypatch.setattr(nodes, "find_places", fake_places)

    events: list[AgentEvent] = []

    async def emit(event: AgentEvent) -> None:
        events.append(event)

    d = Deps(llm=MockProvider(), http=httpx.AsyncClient(), emit=emit, max_revisions=2)
    d.events = events  # type: ignore[attr-defined]
    return d


def _finished(deps) -> list[str]:
    return [e.agent for e in deps.events if e.type == "agent_done"]


async def test_happy_path_runs_each_agent_once(deps, request_):
    itinerary, found = await plan_trip(request_, deps)
    assert _finished(deps) == ["researcher", "planner", "budget", "critic"]
    assert itinerary.critique.approved and itinerary.revisions == 0
    assert itinerary.budget.within_budget
    assert len(itinerary.days) == 3 and len(found) == 12
    assert all(day.weather is not None for day in itinerary.days)
    assert itinerary.llm_provider == "mock"


async def test_critic_sends_plan_back_until_it_fits(deps, request_):
    tight = request_.model_copy(update={"budget_usd": 150})
    itinerary, _ = await plan_trip(tight, deps)
    assert _finished(deps).count("planner") >= 2
    assert itinerary.revisions >= 1
    assert itinerary.budget.within_budget and itinerary.critique.approved


async def test_revisions_are_capped_when_budget_is_impossible(deps, request_):
    impossible = request_.model_copy(update={"budget_usd": 5})
    itinerary, _ = await plan_trip(impossible, deps)
    assert _finished(deps).count("planner") == 3  # first draft + max_revisions
    assert itinerary.revisions == 2
    assert not itinerary.critique.approved and itinerary.critique.issues


async def test_unknown_destination_raises_trip_error(deps, request_):
    with pytest.raises(TripError, match="Nowhereville"):
        await plan_trip(request_.model_copy(update={"destination": "Nowhereville"}), deps)


async def test_refine_skips_research_and_keeps_identity(deps, request_):
    itinerary, found = await plan_trip(request_, deps)
    deps.events.clear()
    refined = await refine_trip(itinerary, found, "make day 1 cheaper", deps)
    assert "researcher" not in _finished(deps)
    assert _finished(deps) == ["planner", "budget", "critic"]
    assert refined.id == itinerary.id and refined.revisions == itinerary.revisions + 1
    assert refined.budget.total_estimated_usd < itinerary.budget.total_estimated_usd
