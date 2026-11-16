"""A rule-based stand-in for a language model.

It lets the whole application run, and its tests pass, with no API key and no cost. It reads
the structured `context` instead of the prompt text and applies simple, deterministic rules:
group nearby sights into days, keep rainy days indoors, cut costs when over budget. It is not
intelligent, and it only understands a few refinement phrases. Switch the provider to
"anthropic" or "bedrock" for real model output.
"""

import re
from datetime import timedelta
from typing import Any

from app.agents.budget import MEAL_CATEGORIES
from app.agents.costs import (
    FREE_CATEGORIES,
    INDOOR_CATEGORIES,
    MEAL_PER_PERSON_USD,
    WET_WEATHER,
    estimate_cost,
)
from app.llm.base import LLMError, T, Task
from app.models.schemas import (
    Activity,
    BudgetReport,
    Critique,
    DayPlan,
    DayWeather,
    Interest,
    Pace,
    Place,
    PlanDraft,
    ResearchBrief,
    TripRequest,
)
from app.tools.geo import distance_km

SIGHTS_PER_DAY = {Pace.RELAXED: 1, Pace.BALANCED: 2, Pace.PACKED: 3}
MAX_LEG_KM = 12.0
_SLOTS = ["morning", "afternoon", "afternoon"]

_CHEAPER = ("cheap", "budget", "less expensive", "save", "afford", "cost")
_RELAX = ("relax", "slow", "fewer", "less busy", "lighter", "rest", "easy")
_MORE = ("more", "add", "busier", "pack", "another")


class MockProvider:
    name = "mock"

    async def generate(
        self,
        *,
        task: Task,
        system: str,
        prompt: str,
        schema: type[T],
        context: dict[str, Any],
    ) -> T:
        if task == "research_brief":
            result = _research_brief(context)
        elif task == "plan":
            result = _plan(context)
        elif task == "critique":
            result = _critique(context)
        else:
            raise LLMError(f"mock provider has no rule for task {task!r}")
        if not isinstance(result, schema):
            raise LLMError(f"mock produced {type(result).__name__}, expected {schema.__name__}")
        return result


# --- research brief -------------------------------------------------------------------------


def _research_brief(ctx: dict[str, Any]) -> ResearchBrief:
    request: TripRequest = ctx["request"]
    places: list[Place] = ctx["places"]
    weather: list[DayWeather] = ctx["weather"]
    where = ctx["location"].name

    counts: dict[str, int] = {}
    for place in places:
        counts[place.interest.value] = counts.get(place.interest.value, 0) + 1
    if places:
        found = ", ".join(f"{n} for {k}" for k, n in counts.items())
        summary = f"Found {len(places)} places in and around {where}: {found}."
    else:
        summary = (
            f"No place data came back for {where}, so the plan uses general suggestions "
            "instead of named sights."
        )
    missing = [i.value for i in request.interests if i.value not in counts]
    if places and missing:
        summary += f" Nothing specific turned up for {', '.join(missing)}."

    known = [d for d in weather if d.temp_max_c is not None]
    if known:
        high = sum(d.temp_max_c for d in known) / len(known)
        low = sum(d.temp_min_c for d in known) / len(known)
        wet = sum(1 for d in known if d.summary in WET_WEATHER)
        kind = "Forecast" if known[0].source == "forecast" else "Typical for these dates"
        note = f"{kind}: highs near {high:.0f}°C, lows near {low:.0f}°C"
        note += f", with {wet} wet day{'s' if wet != 1 else ''}." if wet else ", mostly dry."
    else:
        note = "Weather data was unavailable."

    return ResearchBrief(
        summary=summary, highlights=[p.name for p in places[:6]], weather_note=note
    )


# --- planning -------------------------------------------------------------------------------


def _spend_level(budget: BudgetReport | None, revision: int) -> str:
    if budget is None or budget.within_budget:
        return "standard"
    return "thrifty" if revision <= 1 else "frugal"


def _interleave(places: list[Place], interests: list[Interest]) -> list[Place]:
    """Alternate between interests so every day is not the same kind of sight."""
    groups = {i: [p for p in places if p.interest == i] for i in interests}
    rest = [p for p in places if p.interest not in groups]
    out: list[Place] = []
    while any(groups.values()):
        for interest in interests:
            if groups[interest]:
                out.append(groups[interest].pop(0))
    return out + rest


def _nearest(origin: Place | Activity, candidates: list[Place]) -> Place | None:
    if not candidates or origin.latitude is None:
        return candidates[0] if candidates else None
    return min(
        candidates,
        key=lambda p: distance_km(origin.latitude, origin.longitude, p.latitude, p.longitude),
    )


def _sight_activity(place: Place, slot: str, travelers: int, note: str = "") -> Activity:
    return Activity(
        slot=slot,
        title=f"Visit {place.name}",
        place_name=place.name,
        category=place.category,
        latitude=place.latitude,
        longitude=place.longitude,
        est_cost_usd=estimate_cost(place.category, travelers),
        notes=note,
    )


def _dinner(anchor: Activity | None, food: list[Place], level: str, travelers: int) -> Activity:
    cost = round(MEAL_PER_PERSON_USD[level] * travelers, 2)
    choice = _nearest(anchor, food) if anchor else (food[0] if food else None)
    if choice and level != "frugal":
        food.remove(choice)
        return Activity(
            slot="evening",
            title=f"Dinner at {choice.name}",
            place_name=choice.name,
            category="restaurant",
            latitude=choice.latitude,
            longitude=choice.longitude,
            est_cost_usd=cost,
        )
    title = {
        "standard": "Dinner at a local restaurant",
        "thrifty": "Casual dinner at a neighbourhood spot",
        "frugal": "Street food or a market meal",
    }[level]
    near = f"Look near {anchor.place_name}." if anchor and anchor.place_name else ""
    return Activity(slot="evening", title=title, category="meal", est_cost_usd=cost, notes=near)


def _build_days(ctx: dict[str, Any], level: str) -> list[DayPlan]:
    request: TripRequest = ctx["request"]
    weather: list[DayWeather] = ctx["weather"]
    places: list[Place] = ctx["places"]
    travelers = request.travelers

    food = [p for p in places if p.category in {"restaurant", "cafe"}]
    bars = [p for p in places if p.interest == Interest.NIGHTLIFE]
    sights = [p for p in places if p not in food and p not in bars]
    sights = _interleave(sights, request.interests)
    if level != "standard":
        # Stable sort: free sights first, otherwise keep the interleaved order.
        sights.sort(key=lambda p: p.category not in FREE_CATEGORIES)
    if level == "frugal":
        sights = [p for p in sights if p.category in FREE_CATEGORIES]

    per_day = SIGHTS_PER_DAY[request.pace]
    days: list[DayPlan] = []
    for index in range(request.num_days):
        day_date = request.start_date + timedelta(days=index)
        day_weather = weather[index] if index < len(weather) else None
        wet = bool(day_weather and day_weather.summary in WET_WEATHER)
        activities: list[Activity] = []

        seed: Place | None = None
        for position in range(per_day):
            pool = sights
            if wet:
                pool = [p for p in sights if p.category in INDOOR_CATEGORIES] or sights
            if not pool:
                break
            pick = pool[0] if seed is None else _nearest(seed, pool)
            seed = seed or pick
            sights.remove(pick)
            note = (
                "Indoor pick for a wet day." if wet and pick.category in INDOOR_CATEGORIES else ""
            )
            activities.append(_sight_activity(pick, _SLOTS[position], travelers, note))

        if not activities:
            activities.append(
                Activity(
                    slot="morning",
                    title="Explore the central neighbourhoods on foot",
                    category="walk",
                    notes="No named sights were left for this day.",
                )
            )
        theme = f"Around {seed.name}" if seed else "A free day to wander"

        anchor = activities[-1]
        activities.append(_dinner(anchor, food, level, travelers))
        if bars and level == "standard" and index % 2 == 0:
            bar = _nearest(anchor, bars)
            bars.remove(bar)
            activities.append(
                Activity(
                    slot="evening",
                    title=f"Drinks at {bar.name}",
                    place_name=bar.name,
                    category=bar.category,
                    latitude=bar.latitude,
                    longitude=bar.longitude,
                    est_cost_usd=estimate_cost(bar.category, travelers),
                )
            )
        days.append(DayPlan(date=day_date, theme=theme, activities=activities, weather=day_weather))
    return days


def _plan(ctx: dict[str, Any]) -> PlanDraft:
    request: TripRequest = ctx["request"]
    if ctx.get("feedback") and ctx.get("previous"):
        return _refine(ctx)

    level = _spend_level(ctx.get("budget"), ctx.get("revision", 0))
    days = _build_days(ctx, level)
    where = ctx["location"].name
    overview = f"{request.num_days} days in {where} at a {request.pace.value} pace"
    overview += {
        "standard": ", grouping nearby sights so each day stays in one area.",
        "thrifty": ", reworked around free sights and cheaper meals to fit the budget.",
        "frugal": ", cut back to free sights and market meals to get close to budget.",
    }[level]
    return PlanDraft(overview=overview, days=days)


# --- refinement -----------------------------------------------------------------------------


def _target_days(message: str, total: int) -> list[int]:
    match = re.search(r"day\s*(\d+)", message)
    if match and 1 <= int(match.group(1)) <= total:
        return [int(match.group(1)) - 1]
    return list(range(total))


def _refine(ctx: dict[str, Any]) -> PlanDraft:
    request: TripRequest = ctx["request"]
    message: str = ctx["feedback"].lower()
    days = [day.model_copy(deep=True) for day in ctx["previous"]]
    travelers = request.travelers
    used = {a.place_name for d in days for a in d.activities if a.place_name}
    spare = [
        p for p in ctx["places"] if p.name not in used and p.category not in {"restaurant", "cafe"}
    ]
    targets = _target_days(message, len(days))
    label = f"day {targets[0] + 1}" if len(targets) == 1 else "every day"
    changes = 0

    if any(word in message for word in _CHEAPER):
        free = [p for p in spare if p.category in FREE_CATEGORIES]
        for i in targets:
            for n, activity in enumerate(days[i].activities):
                if activity.category in MEAL_CATEGORIES and activity.est_cost_usd > 0:
                    cheap = round(MEAL_PER_PERSON_USD["thrifty"] * travelers, 2)
                    if activity.est_cost_usd > cheap:
                        days[i].activities[n] = Activity(
                            slot=activity.slot,
                            title="Casual dinner at a neighbourhood spot",
                            category="meal",
                            est_cost_usd=cheap,
                        )
                        changes += 1
                elif activity.est_cost_usd > 0 and free:
                    swap = _nearest(activity, free)
                    free.remove(swap)
                    days[i].activities[n] = _sight_activity(
                        swap,
                        activity.slot,
                        travelers,
                        f"Free alternative to {activity.place_name}.",
                    )
                    changes += 1
        what = f"Made {label} cheaper: {changes} change{'s' if changes != 1 else ''}."
    elif any(word in message for word in _RELAX):
        for i in targets:
            sights = [a for a in days[i].activities if a.slot != "evening"]
            if len(sights) > 1:
                days[i].activities.remove(sights[-1])
                changes += 1
        what = f"Lightened {label}: removed {changes} activit{'ies' if changes != 1 else 'y'}."
    elif any(word in message for word in _MORE):
        for i in targets:
            anchor = next((a for a in days[i].activities if a.latitude is not None), None)
            extra = _nearest(anchor, spare) if anchor else (spare[0] if spare else None)
            if extra:
                spare.remove(extra)
                evening = next(
                    (n for n, a in enumerate(days[i].activities) if a.slot == "evening"),
                    len(days[i].activities),
                )
                days[i].activities.insert(
                    evening, _sight_activity(extra, "afternoon", travelers, "Added on request.")
                )
                changes += 1
        what = f"Added {changes} activit{'ies' if changes != 1 else 'y'} to {label}."
    else:
        what = (
            "No change made. The rule-based planner only understands requests like 'cheaper', "
            "'more relaxed' or 'add more', optionally with 'day 2'. A real model handles free text."
        )
    if changes == 0 and not what.startswith("No change"):
        what += " Nothing suitable was left to change."
    return PlanDraft(overview=what, days=days)


# --- critique -------------------------------------------------------------------------------


def _critique(ctx: dict[str, Any]) -> Critique:
    days: list[DayPlan] = ctx["days"]
    budget: BudgetReport = ctx["budget"]
    issues: list[str] = []
    suggestions: list[str] = []

    if not budget.within_budget:
        issues.append(
            f"Estimated cost ${budget.total_estimated_usd:,.0f} is over the "
            f"${budget.budget_usd:,.0f} budget."
        )
        suggestions.append("Swap paid sights for free ones and choose cheaper meals.")

    for number, day in enumerate(days, start=1):
        located = [a for a in day.activities if a.latitude is not None]
        for first, second in zip(located, located[1:], strict=False):
            leg = distance_km(first.latitude, first.longitude, second.latitude, second.longitude)
            if leg > MAX_LEG_KM:
                issues.append(
                    f"Day {number}: {first.place_name} and {second.place_name} are "
                    f"{leg:.0f} km apart."
                )
                suggestions.append(f"Group day {number} around one neighbourhood.")
        wet = day.weather and day.weather.summary in WET_WEATHER
        outdoor = [
            a.place_name
            for a in day.activities
            if a.place_name and a.slot != "evening" and a.category not in INDOOR_CATEGORIES
        ]
        if wet and outdoor:
            # A warning for the traveller, not a reason to redo the plan.
            suggestions.append(
                f"Day {number} looks wet; {outdoor[0]} is outdoors, so pack a jacket."
            )

    return Critique(approved=not issues, issues=issues, suggestions=suggestions)
