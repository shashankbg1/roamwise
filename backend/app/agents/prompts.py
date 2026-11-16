"""Prompts for the model-backed agents.

Each builder returns (system, user). The rule-based mock ignores these and reads the structured
context instead, so the wording here only matters when a real model is configured.
"""

import json

from app.models.schemas import (
    BudgetReport,
    Critique,
    DayPlan,
    DayWeather,
    Location,
    Place,
    TripRequest,
)

MAX_PLACES_IN_PROMPT = 60


def _places_json(places: list[Place]) -> str:
    rows = [
        {
            "name": p.name,
            "category": p.category,
            "interest": p.interest.value,
            "lat": round(p.latitude, 4),
            "lon": round(p.longitude, 4),
        }
        for p in places[:MAX_PLACES_IN_PROMPT]
    ]
    return json.dumps(rows, ensure_ascii=False)


def _weather_json(weather: list[DayWeather]) -> str:
    return json.dumps([w.model_dump(mode="json") for w in weather])


def _days_json(days: list[DayPlan]) -> str:
    return json.dumps([d.model_dump(mode="json", exclude={"weather"}) for d in days])


def research_prompt(
    request: TripRequest, location: Location, places: list[Place], weather: list[DayWeather]
) -> tuple[str, str]:
    system = (
        "You are a travel researcher. You are given places and weather that were looked up from "
        "live data sources. Summarise what was found for the trip planner. Use only the data "
        "provided: do not invent places, prices or opening hours."
    )
    user = (
        f"Trip request: {request.model_dump_json()}\n"
        f"Destination: {location.model_dump_json()}\n"
        f"Weather by day: {_weather_json(weather)}\n"
        f"Places found: {_places_json(places)}\n\n"
        "Write a two or three sentence summary of what the destination offers for these "
        "interests, list up to six highlights by exact name, and give a one sentence weather note."
    )
    return system, user


def plan_prompt(
    request: TripRequest,
    location: Location,
    places: list[Place],
    weather: list[DayWeather],
    *,
    critique: Critique | None = None,
    budget: BudgetReport | None = None,
    previous: list[DayPlan] | None = None,
    feedback: str | None = None,
) -> tuple[str, str]:
    system = (
        "You are a trip planner. Build a day-by-day itinerary using only the places provided, "
        "referring to each by its exact name and copying its coordinates. Rules:\n"
        "- One DayPlan per trip date, in order.\n"
        "- Group places that are close together into the same day.\n"
        "- Prefer indoor places on wet days.\n"
        "- Respect the pace: relaxed is one daytime sight, balanced two, packed three.\n"
        "- End each day with an evening meal.\n"
        "- est_cost_usd is your estimate for the whole party; use 0 for free sights.\n"
        "- Keep the total within the budget.\n"
        "- Never use a place twice."
    )
    parts = [
        f"Trip request: {request.model_dump_json()}",
        f"Destination: {location.model_dump_json()}",
        f"Weather by day: {_weather_json(weather)}",
        f"Places available: {_places_json(places)}",
    ]
    if previous and feedback:
        parts.append(f"Current itinerary: {_days_json(previous)}")
        parts.append(
            f"The traveller asked for this change: {feedback!r}. Change only what the request "
            "needs and keep everything else. In the overview, say what you changed."
        )
    elif critique and not critique.approved:
        parts.append(f"Your previous draft: {_days_json(previous or [])}")
        if budget:
            parts.append(f"Budget check: {budget.model_dump_json()}")
        parts.append(
            f"A reviewer rejected it. Issues: {critique.issues}. Suggestions: "
            f"{critique.suggestions}. Produce a corrected itinerary."
        )
    else:
        parts.append("Write a one or two sentence overview and the full itinerary.")
    return system, "\n".join(parts)


def critique_prompt(
    request: TripRequest, days: list[DayPlan], budget: BudgetReport
) -> tuple[str, str]:
    system = (
        "You are a strict reviewer of trip itineraries. Approve only if the plan fits the budget, "
        "covers every date, keeps each day's places reasonably close together, suits the stated "
        "interests and pace, and handles wet days sensibly. List concrete issues, each naming the "
        "day it affects, and a matching suggestion. If there are no blocking issues, approve."
    )
    user = (
        f"Trip request: {request.model_dump_json()}\n"
        f"Budget check (computed exactly, trust these numbers): {budget.model_dump_json()}\n"
        f"Itinerary: {json.dumps([d.model_dump(mode='json') for d in days])}"
    )
    return system, user
