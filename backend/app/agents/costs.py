"""Rough per-person price estimates by category, in US dollars.

These are planning heuristics, not quotes. Real prices vary by city and season; the README
says so. They let the budget checker reason about a plan without a paid pricing API.
"""

PER_PERSON_USD: dict[str, float] = {
    "museum": 14,
    "gallery": 12,
    "castle": 12,
    "palace": 12,
    "fort": 10,
    "monastery": 8,
    "convent": 8,
    "archaeological_site": 10,
    "theatre": 35,
    "nightclub": 25,
    "bar": 18,
    "pub": 18,
    "casino": 30,
    "marketplace": 10,
    "mall": 30,
    "department_store": 30,
    "restaurant": 28,
    "cafe": 10,
}
DEFAULT_PER_PERSON_USD = 0.0

# What a dinner costs per person at each spending level.
MEAL_PER_PERSON_USD = {"standard": 28.0, "thrifty": 15.0, "frugal": 9.0}

FREE_CATEGORIES = frozenset(
    {
        "park",
        "garden",
        "viewpoint",
        "beach",
        "nature_reserve",
        "church",
        "cathedral",
        "monument",
        "memorial",
        "ruins",
        "historic_site",
        "synagogue",
        "mosque",
        "temple",
        "walk",
    }
)
INDOOR_CATEGORIES = frozenset(
    {
        "museum",
        "gallery",
        "palace",
        "castle",
        "church",
        "cathedral",
        "monastery",
        "convent",
        "synagogue",
        "mosque",
        "temple",
        "theatre",
        "mall",
        "department_store",
        "marketplace",
    }
)
WET_WEATHER = frozenset({"Rain", "Drizzle", "Thunderstorm", "Snow"})


def estimate_cost(category: str, travelers: int) -> float:
    """Estimated cost of one activity for the whole party."""
    return round(PER_PERSON_USD.get(category, DEFAULT_PER_PERSON_USD) * travelers, 2)
