from app.agents.budget import compute_budget
from app.agents.costs import INDOOR_CATEGORIES
from app.llm.mock import MockProvider
from app.models.schemas import Critique, Pace, PlanDraft, ResearchBrief


async def _plan(ctx) -> PlanDraft:
    return await MockProvider().generate(
        task="plan", system="", prompt="", schema=PlanDraft, context=ctx
    )


def _ctx(request_, location, places, weather, **extra):
    return {
        "request": request_,
        "location": location,
        "places": list(places),
        "weather": weather,
        **extra,
    }


async def test_brief_reports_counts_and_weather(request_, location, places, weather):
    brief = await MockProvider().generate(
        task="research_brief",
        system="",
        prompt="",
        schema=ResearchBrief,
        context=_ctx(request_, location, places, weather),
    )
    assert "12 places" in brief.summary
    assert "1 wet day" in brief.weather_note
    assert brief.highlights[0] == "São Jorge Castle"


async def test_plan_covers_every_day_without_repeats(request_, location, places, weather):
    draft = await _plan(_ctx(request_, location, places, weather))
    assert [d.date for d in draft.days] == [w.date for w in weather]
    named = [a.place_name for d in draft.days for a in d.activities if a.place_name]
    assert len(named) == len(set(named))
    assert all(any(a.slot == "evening" for a in d.activities) for d in draft.days)


async def test_wet_day_gets_indoor_sights(request_, location, places, weather):
    draft = await _plan(_ctx(request_, location, places, weather))
    rainy = draft.days[1]
    daytime = [a for a in rainy.activities if a.slot != "evening"]
    assert daytime and all(a.category in INDOOR_CATEGORIES for a in daytime)


async def test_pace_changes_how_much_is_planned(request_, location, places, weather):
    relaxed = await _plan(
        _ctx(request_.model_copy(update={"pace": Pace.RELAXED}), location, places, weather)
    )
    packed = await _plan(
        _ctx(request_.model_copy(update={"pace": Pace.PACKED}), location, places, weather)
    )
    count = lambda draft: sum(len(d.activities) for d in draft.days)  # noqa: E731
    assert count(packed) > count(relaxed)


async def test_replanning_over_budget_is_cheaper(request_, location, places, weather):
    tight = request_.model_copy(update={"budget_usd": 150})
    first = await _plan(_ctx(tight, location, places, weather))
    report = compute_budget(tight, first.days)
    assert not report.within_budget
    second = await _plan(_ctx(tight, location, places, weather, budget=report, revision=1))
    assert compute_budget(tight, second.days).total_estimated_usd < report.total_estimated_usd


async def test_plan_without_place_data_still_fills_days(request_, location, weather):
    draft = await _plan(_ctx(request_, location, [], weather))
    assert len(draft.days) == 3
    assert all(d.activities for d in draft.days)


async def test_critic_flags_over_budget_only_when_over(request_, location, places, weather):
    draft = await _plan(_ctx(request_, location, places, weather))
    for budget_usd, expected in [(5000, True), (20, False)]:
        req = request_.model_copy(update={"budget_usd": budget_usd})
        critique = await MockProvider().generate(
            task="critique",
            system="",
            prompt="",
            schema=Critique,
            context={"request": req, "days": draft.days, "budget": compute_budget(req, draft.days)},
        )
        assert critique.approved is expected


async def test_refine_cheaper_targets_one_day(request_, location, places, weather):
    draft = await _plan(_ctx(request_, location, places, weather))
    refined = await _plan(
        _ctx(
            request_,
            location,
            places,
            weather,
            previous=draft.days,
            feedback="Make day 1 cheaper",
        )
    )
    assert refined.days[0].cost_usd < draft.days[0].cost_usd
    assert refined.days[1] == draft.days[1] and refined.days[2] == draft.days[2]
    assert "day 1" in refined.overview


async def test_refine_relaxed_removes_an_activity(request_, location, places, weather):
    draft = await _plan(_ctx(request_, location, places, weather))
    refined = await _plan(
        _ctx(request_, location, places, weather, previous=draft.days, feedback="more relaxed")
    )
    assert sum(len(d.activities) for d in refined.days) < sum(len(d.activities) for d in draft.days)


async def test_refine_unknown_request_says_so(request_, location, places, weather):
    draft = await _plan(_ctx(request_, location, places, weather))
    refined = await _plan(
        _ctx(request_, location, places, weather, previous=draft.days, feedback="xyzzy plugh")
    )
    assert refined.days == draft.days
    assert refined.overview.startswith("No change made")
