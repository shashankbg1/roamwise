"""The four agents, as LangGraph nodes.

Each node reads the shared state, does its job, reports progress through `emit`, and returns
only the keys it changed.
"""

import asyncio

from langchain_core.runnables import RunnableConfig

from app.agents import prompts
from app.agents.budget import compute_budget
from app.agents.state import TripError, TripState, deps_from
from app.models.schemas import AgentEvent, Critique, PlanDraft, ResearchBrief
from app.tools.geocode import geocode
from app.tools.places import find_places
from app.tools.weather import get_weather


async def researcher(state: TripState, config: RunnableConfig) -> TripState:
    deps = deps_from(config)
    request = state["request"]
    emit = deps.emit

    await emit(_status("researcher", f"Looking up {request.destination}"))
    location = await geocode(deps.http, request.destination)
    if location is None:
        raise TripError(
            f"Couldn't find a place called {request.destination!r}. Check the spelling."
        )
    where = f"{location.name}, {location.country}" if location.country else location.name
    await emit(_tool("researcher", f"Geocoding: found {where}"))

    await emit(_status("researcher", "Checking the weather and searching for places"))
    weather, places = await asyncio.gather(
        get_weather(deps.http, location, request.start_date, request.end_date),
        find_places(deps.http, location, request.interests),
    )
    source = weather[0].source if weather else "unavailable"
    await emit(_tool("researcher", f"Weather: {len(weather)} days ({source})"))
    await emit(_tool("researcher", f"Places: {len(places)} found"))

    system, user = prompts.research_prompt(request, location, places, weather)
    brief = await deps.llm.generate(
        task="research_brief",
        system=system,
        prompt=user,
        schema=ResearchBrief,
        context={"request": request, "location": location, "places": places, "weather": weather},
    )
    await emit(_done("researcher", brief.summary))
    return {"location": location, "weather": weather, "places": places, "brief": brief}


async def planner(state: TripState, config: RunnableConfig) -> TripState:
    deps = deps_from(config)
    attempts = state.get("attempts", 0) + 1
    critique = state.get("critique")
    feedback = state.get("feedback")
    refining = bool(feedback and state.get("previous"))

    if refining:
        await deps.emit(_status("planner", f"Revising the plan: {feedback}"))
    elif attempts == 1:
        await deps.emit(_status("planner", "Drafting the day-by-day plan"))
    else:
        await deps.emit(_status("planner", f"Reworking the plan (revision {attempts - 1})"))

    previous = state.get("previous") if refining else state.get("days")
    system, user = prompts.plan_prompt(
        state["request"],
        state["location"],
        state["places"],
        state["weather"],
        critique=None if refining else critique,
        budget=state.get("budget"),
        previous=previous,
        feedback=feedback if refining else None,
    )
    draft = await deps.llm.generate(
        task="plan",
        system=system,
        prompt=user,
        schema=PlanDraft,
        context={
            "request": state["request"],
            "location": state["location"],
            "places": list(state["places"]),
            "weather": state["weather"],
            "budget": None if refining else state.get("budget"),
            "revision": attempts - 1,
            "previous": previous,
            "feedback": feedback if refining else None,
        },
    )
    # Weather is attached here, from the looked-up data, so a model can never invent it.
    by_date = {w.date: w for w in state["weather"]}
    days = [day.model_copy(update={"weather": by_date.get(day.date)}) for day in draft.days]
    count = sum(len(d.activities) for d in days)
    await deps.emit(_done("planner", f"{len(days)} days, {count} activities. {draft.overview}"))
    return {"overview": draft.overview, "days": days, "attempts": attempts}


async def budget(state: TripState, config: RunnableConfig) -> TripState:
    deps = deps_from(config)
    await deps.emit(_status("budget", "Adding up the costs"))
    report = compute_budget(state["request"], state["days"])
    verdict = "within" if report.within_budget else "over"
    await deps.emit(
        _done(
            "budget",
            f"${report.total_estimated_usd:,.0f} estimated, {verdict} the "
            f"${report.budget_usd:,.0f} budget",
        )
    )
    return {"budget": report}


async def critic(state: TripState, config: RunnableConfig) -> TripState:
    deps = deps_from(config)
    await deps.emit(_status("critic", "Reviewing the plan"))
    system, user = prompts.critique_prompt(state["request"], state["days"], state["budget"])
    critique = await deps.llm.generate(
        task="critique",
        system=system,
        prompt=user,
        schema=Critique,
        context={"request": state["request"], "days": state["days"], "budget": state["budget"]},
    )
    if critique.approved:
        message = "Approved"
    else:
        message = "Sent back: " + "; ".join(critique.issues)
    await deps.emit(_done("critic", message))
    return {"critique": critique}


def _status(agent: str, message: str) -> AgentEvent:
    return AgentEvent(type="status", agent=agent, message=message)


def _tool(agent: str, message: str) -> AgentEvent:
    return AgentEvent(type="tool", agent=agent, message=message)


def _done(agent: str, message: str) -> AgentEvent:
    return AgentEvent(type="agent_done", agent=agent, message=message)
