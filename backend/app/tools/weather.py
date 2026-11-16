"""Daily weather for a trip, from Open-Meteo (no key needed).

Forecasts only reach about two weeks ahead. For trips further out we fall back to what the
weather was on the same dates in the most recent past year and label it "typical".
"""

from datetime import date, timedelta

import httpx

from app.models.schemas import DayWeather, Location

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_HORIZON_DAYS = 15
# The archive lags real time by a few days.
ARCHIVE_LAG_DAYS = 7
DAILY_FIELDS = "temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code"

# WMO weather interpretation codes, grouped.
_WMO = [
    ({0}, "Clear"),
    ({1, 2}, "Partly cloudy"),
    ({3}, "Overcast"),
    ({45, 48}, "Fog"),
    ({51, 53, 55, 56, 57}, "Drizzle"),
    ({61, 63, 65, 66, 67, 80, 81, 82}, "Rain"),
    ({71, 73, 75, 77, 85, 86}, "Snow"),
    ({95, 96, 99}, "Thunderstorm"),
]


def describe_weather_code(code: int | None) -> str:
    for codes, label in _WMO:
        if code in codes:
            return label
    return "Unknown"


def _shift_to_past(start: date, end: date, today: date) -> tuple[date, date, int]:
    """Move a date range back by whole years until the archive covers it."""
    latest = today - timedelta(days=ARCHIVE_LAG_DAYS)
    years = 0
    while end > latest:
        years += 1
        try:
            end = end.replace(year=end.year - 1)
            start = start.replace(year=start.year - 1)
        except ValueError:  # 29 February in a non-leap year
            end -= timedelta(days=365)
            start -= timedelta(days=365)
    return start, end, years


def _unavailable(start: date, end: date) -> list[DayWeather]:
    days = (end - start).days + 1
    return [
        DayWeather(
            date=start + timedelta(days=i), summary="Weather unavailable", source="unavailable"
        )
        for i in range(days)
    ]


async def get_weather(
    client: httpx.AsyncClient,
    location: Location,
    start: date,
    end: date,
    today: date | None = None,
) -> list[DayWeather]:
    """Return one DayWeather per trip day. Never raises: failures come back as 'unavailable'."""
    today = today or date.today()
    use_forecast = start >= today and end <= today + timedelta(days=FORECAST_HORIZON_DAYS)
    if use_forecast:
        url, query_start, query_end, source = FORECAST_URL, start, end, "forecast"
    else:
        query_start, query_end, _ = _shift_to_past(start, end, today)
        url, source = ARCHIVE_URL, "typical"

    try:
        response = await client.get(
            url,
            params={
                "latitude": location.latitude,
                "longitude": location.longitude,
                "daily": DAILY_FIELDS,
                "timezone": "auto",
                "start_date": query_start.isoformat(),
                "end_date": query_end.isoformat(),
            },
        )
        response.raise_for_status()
        daily = response.json()["daily"]
    except (httpx.HTTPError, KeyError, ValueError):
        return _unavailable(start, end)

    num_days = (end - start).days + 1
    out: list[DayWeather] = []
    for i in range(num_days):
        try:
            out.append(
                DayWeather(
                    date=start + timedelta(days=i),
                    temp_max_c=daily["temperature_2m_max"][i],
                    temp_min_c=daily["temperature_2m_min"][i],
                    precipitation_mm=daily["precipitation_sum"][i],
                    summary=describe_weather_code(daily["weather_code"][i]),
                    source=source,
                )
            )
        except (IndexError, KeyError):
            out.extend(_unavailable(start + timedelta(days=i), start + timedelta(days=i)))
    return out
