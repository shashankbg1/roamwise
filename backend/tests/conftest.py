"""Shared fixtures: a small, fixed set of Lisbon data so tests never touch the network."""

from datetime import date, timedelta

import pytest

from app.models.schemas import DayWeather, Interest, Location, Place, TripRequest

START = date(2027, 3, 1)


def make_place(name, category, interest, lat, lon, notable=True) -> Place:
    return Place(
        name=name,
        category=category,
        interest=interest,
        latitude=lat,
        longitude=lon,
        notable=notable,
    )


@pytest.fixture
def location() -> Location:
    return Location(name="Lisbon", country="Portugal", latitude=38.7251, longitude=-9.1498)


@pytest.fixture
def places() -> list[Place]:
    h, n, f = Interest.HISTORY, Interest.NATURE, Interest.FOOD
    return [
        make_place("São Jorge Castle", "castle", h, 38.7139, -9.1335),
        make_place("Lisbon Cathedral", "cathedral", h, 38.7098, -9.1326),
        make_place("National Tile Museum", "museum", h, 38.7249, -9.1136),
        make_place("Carmo Convent", "convent", h, 38.7120, -9.1404),
        make_place("Belém Tower", "fort", h, 38.6916, -9.2160),
        make_place("Jerónimos Monastery", "monastery", h, 38.6979, -9.2068),
        make_place("Edward VII Park", "park", n, 38.7283, -9.1527),
        make_place("Estrela Garden", "garden", n, 38.7143, -9.1596),
        make_place("Miradouro da Graça", "viewpoint", n, 38.7163, -9.1313),
        make_place("Tasca do Chico", "restaurant", f, 38.7118, -9.1437, notable=False),
        make_place("Time Out Market", "marketplace", f, 38.7069, -9.1459),
        make_place("Cervejaria Ramiro", "restaurant", f, 38.7205, -9.1357, notable=False),
    ]


@pytest.fixture
def request_() -> TripRequest:
    return TripRequest(
        destination="Lisbon",
        start_date=START,
        end_date=START + timedelta(days=2),
        budget_usd=600,
        travelers=2,
        interests=[Interest.HISTORY, Interest.NATURE, Interest.FOOD],
    )


@pytest.fixture
def weather() -> list[DayWeather]:
    summaries = ["Clear", "Rain", "Partly cloudy"]
    return [
        DayWeather(
            date=START + timedelta(days=i),
            temp_max_c=18,
            temp_min_c=10,
            precipitation_mm=12 if s == "Rain" else 0,
            summary=s,
            source="typical",
        )
        for i, s in enumerate(summaries)
    ]
