from datetime import date

import pytest
from pydantic import ValidationError

from app.models.schemas import Activity, DayPlan, TripRequest


def _request(**overrides):
    base = {
        "destination": "Lisbon",
        "start_date": date(2027, 3, 1),
        "end_date": date(2027, 3, 5),
        "budget_usd": 1200,
    }
    return TripRequest(**(base | overrides))


def test_num_days_counts_both_ends():
    assert _request().num_days == 5


def test_end_before_start_is_rejected():
    with pytest.raises(ValidationError, match="end_date"):
        _request(end_date=date(2027, 2, 27))


def test_trip_length_is_capped():
    with pytest.raises(ValidationError, match="limited"):
        _request(end_date=date(2027, 4, 1))


def test_budget_must_be_positive():
    with pytest.raises(ValidationError):
        _request(budget_usd=0)


def test_day_cost_sums_activities():
    day = DayPlan(
        date=date(2027, 3, 1),
        theme="Old town",
        activities=[
            Activity(slot="morning", title="Museum", category="museum", est_cost_usd=15),
            Activity(slot="evening", title="Dinner", category="restaurant", est_cost_usd=42.5),
        ],
    )
    assert day.cost_usd == 57.5
