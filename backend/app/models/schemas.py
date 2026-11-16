"""The data shapes shared by the API, the agents and storage."""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

MAX_TRIP_DAYS = 14


class Interest(StrEnum):
    HISTORY = "history"
    FOOD = "food"
    NATURE = "nature"
    ART = "art"
    NIGHTLIFE = "nightlife"
    SHOPPING = "shopping"


class Pace(StrEnum):
    RELAXED = "relaxed"
    BALANCED = "balanced"
    PACKED = "packed"


class TripRequest(BaseModel):
    """What the traveller asks for."""

    destination: str = Field(min_length=2, max_length=80)
    start_date: date
    end_date: date
    budget_usd: float = Field(gt=0, le=100_000, description="Total budget for activities and food")
    travelers: int = Field(default=1, ge=1, le=12)
    interests: list[Interest] = Field(default_factory=lambda: [Interest.HISTORY, Interest.FOOD])
    pace: Pace = Pace.BALANCED

    @model_validator(mode="after")
    def _check_dates(self) -> TripRequest:
        if self.end_date < self.start_date:
            raise ValueError("end_date must not be before start_date")
        if self.num_days > MAX_TRIP_DAYS:
            raise ValueError(f"trips are limited to {MAX_TRIP_DAYS} days")
        return self

    @property
    def num_days(self) -> int:
        return (self.end_date - self.start_date).days + 1


class Location(BaseModel):
    """A destination resolved to coordinates."""

    name: str
    country: str | None = None
    latitude: float
    longitude: float
    timezone: str | None = None


class DayWeather(BaseModel):
    date: date
    temp_max_c: float | None = None
    temp_min_c: float | None = None
    precipitation_mm: float | None = None
    summary: str
    # "forecast" for the next two weeks; "typical" when based on the same dates last year.
    source: Literal["forecast", "typical", "unavailable"] = "forecast"


class Place(BaseModel):
    """A point of interest found near the destination."""

    name: str
    category: str
    interest: Interest
    latitude: float
    longitude: float
    # True when the place has a Wikipedia or Wikidata entry, a rough proxy for being well known.
    notable: bool = False
    website: str | None = None


class Activity(BaseModel):
    slot: Literal["morning", "afternoon", "evening"]
    title: str
    place_name: str | None = None
    category: str
    latitude: float | None = None
    longitude: float | None = None
    est_cost_usd: float = Field(default=0, ge=0, description="Estimated cost for the whole party")
    notes: str = ""


class DayPlan(BaseModel):
    date: date
    theme: str
    activities: list[Activity] = Field(default_factory=list)
    weather: DayWeather | None = None

    @property
    def cost_usd(self) -> float:
        return round(sum(a.est_cost_usd for a in self.activities), 2)


class ResearchBrief(BaseModel):
    """The researcher's summary of what it found."""

    summary: str
    highlights: list[str] = Field(default_factory=list)
    weather_note: str = ""


class PlanDraft(BaseModel):
    """What the planner produces: the days plus a short overview."""

    overview: str
    days: list[DayPlan]


class BudgetReport(BaseModel):
    budget_usd: float
    total_estimated_usd: float
    per_day_usd: list[float]
    by_category_usd: dict[str, float]
    within_budget: bool
    notes: list[str] = Field(default_factory=list)


class Critique(BaseModel):
    approved: bool
    issues: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class Itinerary(BaseModel):
    """A finished trip plan, as stored and returned by the API."""

    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    request: TripRequest
    location: Location
    overview: str
    brief: ResearchBrief
    days: list[DayPlan]
    budget: BudgetReport
    critique: Critique
    revisions: int = 0
    llm_provider: str = "mock"


class RefineRequest(BaseModel):
    message: str = Field(min_length=2, max_length=500)


class TripSummary(BaseModel):
    """A row in the saved-trips list."""

    id: str
    destination: str
    start_date: date
    end_date: date
    total_estimated_usd: float
    created_at: datetime


class AgentEvent(BaseModel):
    """One progress update streamed to the browser while the agents work."""

    type: Literal["status", "tool", "agent_done", "final", "error"]
    agent: Literal["researcher", "planner", "budget", "critic", "system"]
    message: str
    data: dict | None = None
