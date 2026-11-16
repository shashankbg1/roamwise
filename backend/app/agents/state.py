"""Shared state and runtime dependencies for the agent graph."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypedDict

import httpx
from langchain_core.runnables import RunnableConfig

from app.llm.base import LLMProvider
from app.models.schemas import (
    AgentEvent,
    BudgetReport,
    Critique,
    DayPlan,
    DayWeather,
    Location,
    Place,
    ResearchBrief,
    TripRequest,
)

Emit = Callable[[AgentEvent], Awaitable[None]]


class TripError(Exception):
    """A problem the traveller can act on, such as a destination that cannot be found."""


class TripState(TypedDict, total=False):
    """Everything the agents read and write. Each node returns only the keys it changes."""

    request: TripRequest
    location: Location
    weather: list[DayWeather]
    places: list[Place]
    brief: ResearchBrief
    overview: str
    days: list[DayPlan]
    budget: BudgetReport
    critique: Critique
    # How many times the planner has run. Revisions = attempts - 1.
    attempts: int
    # Set only when refining a saved plan.
    feedback: str
    previous: list[DayPlan]


@dataclass
class Deps:
    """Things nodes need but that do not belong in the state: clients and callbacks."""

    llm: LLMProvider
    http: httpx.AsyncClient
    emit: Emit
    max_revisions: int = 2


def deps_from(config: RunnableConfig) -> Deps:
    return config["configurable"]["deps"]
