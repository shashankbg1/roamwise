"""The budget checker. Arithmetic is done in code, not by a model, so the totals are exact."""

from collections import defaultdict

from app.models.schemas import BudgetReport, DayPlan, TripRequest

MEAL_CATEGORIES = {"restaurant", "cafe", "meal"}


def compute_budget(request: TripRequest, days: list[DayPlan]) -> BudgetReport:
    per_day = [day.cost_usd for day in days]
    total = round(sum(per_day), 2)
    by_category: dict[str, float] = defaultdict(float)
    for day in days:
        for activity in day.activities:
            if activity.est_cost_usd:
                by_category[activity.category] += activity.est_cost_usd
    by_category = {k: round(v, 2) for k, v in sorted(by_category.items(), key=lambda kv: -kv[1])}

    within = total <= request.budget_usd
    notes: list[str] = []
    if within:
        spare = request.budget_usd - total
        notes.append(f"${spare:,.0f} of the budget is left for transport, snacks and extras.")
    else:
        over = total - request.budget_usd
        notes.append(f"The plan is ${over:,.0f} over budget.")
        if by_category:
            top = next(iter(by_category))
            notes.append(
                f"The largest cost is {top.replace('_', ' ')} at ${by_category[top]:,.0f}."
            )
    if days:
        priciest = max(range(len(days)), key=lambda i: per_day[i])
        if per_day[priciest] > 0:
            notes.append(f"Day {priciest + 1} is the most expensive at ${per_day[priciest]:,.0f}.")
    notes.append("Costs are rough estimates and exclude flights and accommodation.")

    return BudgetReport(
        budget_usd=request.budget_usd,
        total_estimated_usd=total,
        per_day_usd=per_day,
        by_category_usd=by_category,
        within_budget=within,
        notes=notes,
    )
