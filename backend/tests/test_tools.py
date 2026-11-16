"""Tool tests. All HTTP is served by httpx.MockTransport, so they run offline."""

from datetime import date

import httpx

from app.models.schemas import Interest, Location
from app.tools.geocode import geocode
from app.tools.places import (
    build_query,
    find_places,
    find_places_overpass,
    merge_places,
    parse_elements,
)
from app.tools.weather import _shift_to_past, describe_weather_code, get_weather
from app.tools.wikipedia import classify, parse_pages

LISBON = Location(name="Lisbon", country="Portugal", latitude=38.72, longitude=-9.14)


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_geocode_returns_top_match():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["name"] == "Lisbon"
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "name": "Lisbon",
                        "country": "Portugal",
                        "latitude": 38.72,
                        "longitude": -9.14,
                        "timezone": "Europe/Lisbon",
                    }
                ]
            },
        )

    async with _client(handler) as client:
        location = await geocode(client, "Lisbon")
    assert location is not None
    assert location.country == "Portugal"
    assert location.timezone == "Europe/Lisbon"


async def test_geocode_unknown_place_returns_none():
    async with _client(lambda r: httpx.Response(200, json={})) as client:
        assert await geocode(client, "Xyzzyville") is None


def _daily(n: int) -> dict:
    return {
        "daily": {
            "temperature_2m_max": [20.0 + i for i in range(n)],
            "temperature_2m_min": [10.0 + i for i in range(n)],
            "precipitation_sum": [0.0] * n,
            "weather_code": [0, 61, 3][:n] + [0] * max(0, n - 3),
        }
    }


async def test_weather_uses_forecast_for_near_dates():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["host"] = request.url.host
        return httpx.Response(200, json=_daily(3))

    async with _client(handler) as client:
        days = await get_weather(
            client, LISBON, date(2027, 3, 2), date(2027, 3, 4), today=date(2027, 3, 1)
        )
    assert seen["host"] == "api.open-meteo.com"
    assert [d.summary for d in days] == ["Clear", "Rain", "Overcast"]
    assert all(d.source == "forecast" for d in days)
    assert days[1].temp_max_c == 21.0


async def test_weather_falls_back_to_last_year_for_far_dates():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["host"] = request.url.host
        seen["start"] = request.url.params["start_date"]
        return httpx.Response(200, json=_daily(2))

    async with _client(handler) as client:
        days = await get_weather(
            client, LISBON, date(2027, 9, 1), date(2027, 9, 2), today=date(2027, 3, 1)
        )
    assert seen["host"] == "archive-api.open-meteo.com"
    assert seen["start"] == "2026-09-01"
    assert [d.date for d in days] == [date(2027, 9, 1), date(2027, 9, 2)]
    assert all(d.source == "typical" for d in days)


async def test_weather_failure_is_reported_not_raised():
    async with _client(lambda r: httpx.Response(500)) as client:
        days = await get_weather(
            client, LISBON, date(2027, 3, 2), date(2027, 3, 3), today=date(2027, 3, 1)
        )
    assert len(days) == 2
    assert all(d.source == "unavailable" for d in days)


def test_shift_to_past_handles_leap_day():
    start, end, years = _shift_to_past(date(2028, 2, 29), date(2028, 2, 29), date(2027, 3, 1))
    assert years == 2
    assert end < date(2027, 3, 1)


def test_weather_code_labels():
    assert describe_weather_code(95) == "Thunderstorm"
    assert describe_weather_code(None) == "Unknown"


ELEMENTS = [
    {"type": "node", "lat": 38.71, "lon": -9.13, "tags": {"name": "Cafe A", "amenity": "cafe"}},
    {
        "type": "way",
        "center": {"lat": 38.69, "lon": -9.21},
        "tags": {"name": "Belém Tower", "historic": "fort", "wikidata": "Q1"},
    },
    {"type": "node", "lat": 38.7, "lon": -9.1, "tags": {"amenity": "cafe"}},
    {"type": "node", "lat": 38.7, "lon": -9.1, "tags": {"name": "cafe a", "amenity": "cafe"}},
]


def test_parse_elements_filters_dedupes_and_ranks():
    places = parse_elements(ELEMENTS, [Interest.HISTORY, Interest.FOOD])
    assert [p.name for p in places] == ["Belém Tower", "Cafe A"]
    assert places[0].notable and places[0].interest == Interest.HISTORY
    assert places[0].latitude == 38.69
    assert places[1].interest == Interest.FOOD


def test_build_query_has_one_block_per_interest():
    query = build_query(LISBON, [Interest.NATURE, Interest.NIGHTLIFE])
    assert query.count("out center tags") == 2
    assert "around:6000,38.72,-9.14" in query


async def test_overpass_tries_second_mirror():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.host)
        if len(calls) == 1:
            return httpx.Response(504)
        return httpx.Response(200, json={"elements": ELEMENTS})

    async with _client(handler) as client:
        places = await find_places_overpass(client, LISBON, [Interest.FOOD])
    assert len(calls) == 2 and calls[0] != calls[1]
    assert len(places) == 2


PAGES = [
    {
        "pageid": 1,
        "index": 2,
        "title": "Edward VII Park",
        "description": "Park in Lisbon, Portugal",
        "coordinates": [{"lat": 38.728, "lon": -9.152}],
    },
    {
        "pageid": 2,
        "index": 1,
        "title": "Bemposta Palace",
        "description": "Palace in Lisbon",
        "coordinates": [{"lat": 38.723, "lon": -9.137}],
    },
    {
        "pageid": 3,
        "index": 3,
        "title": "Camões Secondary School",
        "description": "Secondary School in Lisbon, Portugal",
        "coordinates": [{"lat": 38.73, "lon": -9.14}],
    },
    {"pageid": 4, "index": 4, "title": "No description"},
]


def test_classify_keeps_sights_and_drops_noise():
    wanted = [Interest.HISTORY, Interest.NATURE]
    assert classify("Palace in Lisbon", wanted) == ("palace", Interest.HISTORY)
    assert classify("Park in Lisbon, Portugal", wanted) == ("park", Interest.NATURE)
    assert classify("Secondary School in Lisbon", wanted) is None
    assert classify("Business park in Lisbon", wanted) is None
    assert classify(None, wanted) is None
    # A palace is not offered to someone who only asked for nature.
    assert classify("Palace in Lisbon", [Interest.NATURE]) is None
    # Museums serve art lovers when history was not requested.
    assert classify("Museum in Lisbon", [Interest.ART]) == ("museum", Interest.ART)


def test_parse_pages_builds_places():
    places = parse_pages(PAGES, [Interest.HISTORY, Interest.NATURE])
    assert [p.name for p in places] == ["Edward VII Park", "Bemposta Palace"]
    assert all(p.notable for p in places)


def test_merge_places_dedupes_across_sources():
    wiki = parse_pages(PAGES, [Interest.HISTORY, Interest.NATURE])
    osm = parse_elements(ELEMENTS, [Interest.HISTORY, Interest.FOOD])
    duplicate = osm[0].model_copy(update={"name": "bemposta palace"})
    merged = merge_places(wiki, osm + [duplicate])
    names = [p.name for p in merged]
    assert names.count("Bemposta Palace") == 1 and "bemposta palace" not in names
    assert names[-1] == "Cafe A"  # the only place without a Wikipedia or Wikidata entry


async def test_find_places_survives_overpass_outage():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "en.wikipedia.org":
            return httpx.Response(
                200, json={"query": {"pages": {str(p["pageid"]): p for p in PAGES}}}
            )
        return httpx.Response(504)

    async with _client(handler) as client:
        places = await find_places(client, LISBON, [Interest.HISTORY, Interest.NATURE])
    assert [p.name for p in places] == ["Bemposta Palace", "Edward VII Park"]


async def test_find_places_returns_empty_when_everything_fails():
    async with _client(lambda r: httpx.Response(500)) as client:
        assert await find_places(client, LISBON, [Interest.FOOD]) == []
