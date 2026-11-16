"""Find notable places near a destination from Wikipedia's geosearch API (no key needed).

Wikipedia returns every article with coordinates, so most results are noise (schools, parishes,
companies). We keep only articles whose short description matches a sightseeing keyword.
"""

import httpx

from app.models.schemas import Interest, Location, Place

WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
SEARCH_RADIUS_M = 10000

# (keyword in the article description, category label, interest), checked in order.
_KEYWORDS: list[tuple[str, str, Interest]] = [
    ("castle", "castle", Interest.HISTORY),
    ("palace", "palace", Interest.HISTORY),
    ("fort", "fort", Interest.HISTORY),
    ("monastery", "monastery", Interest.HISTORY),
    ("convent", "convent", Interest.HISTORY),
    ("cathedral", "cathedral", Interest.HISTORY),
    ("basilica", "church", Interest.HISTORY),
    ("church", "church", Interest.HISTORY),
    ("synagogue", "synagogue", Interest.HISTORY),
    ("mosque", "mosque", Interest.HISTORY),
    ("temple", "temple", Interest.HISTORY),
    ("monument", "monument", Interest.HISTORY),
    ("memorial", "memorial", Interest.HISTORY),
    ("ruins", "ruins", Interest.HISTORY),
    ("archaeological", "archaeological_site", Interest.HISTORY),
    ("aqueduct", "monument", Interest.HISTORY),
    ("historic", "historic_site", Interest.HISTORY),
    ("art museum", "gallery", Interest.ART),
    ("gallery", "gallery", Interest.ART),
    ("museum", "museum", Interest.HISTORY),
    ("opera", "theatre", Interest.ART),
    ("theatre", "theatre", Interest.ART),
    ("theater", "theatre", Interest.ART),
    ("concert hall", "theatre", Interest.ART),
    ("botanical", "garden", Interest.NATURE),
    ("garden", "garden", Interest.NATURE),
    ("park", "park", Interest.NATURE),
    ("viewpoint", "viewpoint", Interest.NATURE),
    ("beach", "beach", Interest.NATURE),
    ("nature reserve", "nature_reserve", Interest.NATURE),
    ("nightclub", "nightclub", Interest.NIGHTLIFE),
    ("jazz club", "bar", Interest.NIGHTLIFE),
    ("casino", "casino", Interest.NIGHTLIFE),
    ("market", "marketplace", Interest.FOOD),
    ("shopping", "mall", Interest.SHOPPING),
    ("department store", "department_store", Interest.SHOPPING),
]
# Descriptions containing these are never sights, whatever else they mention.
_EXCLUDE = (
    "school",
    "university",
    "hospital",
    "station",
    "parish",
    "company",
    "football",
    "stadium",
    "embassy",
    "political",
    "newspaper",
    "airline",
    "business park",
    "industrial park",
    "car park",
)
# Museums count for art lovers as well as history lovers.
_ALSO: dict[str, Interest] = {"museum": Interest.ART, "marketplace": Interest.SHOPPING}


def classify(description: str | None, wanted: list[Interest]) -> tuple[str, Interest] | None:
    """Return (category, interest) for a description, or None if it is not a sight we want."""
    if not description:
        return None
    text = description.lower()
    if any(word in text for word in _EXCLUDE):
        return None
    for keyword, category, interest in _KEYWORDS:
        if keyword in text:
            if interest in wanted:
                return category, interest
            alternative = _ALSO.get(category)
            if alternative in wanted:
                return category, alternative
            return None
    return None


def parse_pages(pages: list[dict], interests: list[Interest]) -> list[Place]:
    places: list[Place] = []
    for page in pages:
        coords = (page.get("coordinates") or [{}])[0]
        match = classify(page.get("description"), interests)
        if match is None or "lat" not in coords:
            continue
        category, interest = match
        places.append(
            Place(
                name=page["title"],
                category=category,
                interest=interest,
                latitude=coords["lat"],
                longitude=coords["lon"],
                notable=True,
                website=f"https://en.wikipedia.org/?curid={page['pageid']}",
            )
        )
    return places


async def find_places_wikipedia(
    client: httpx.AsyncClient, location: Location, interests: list[Interest]
) -> list[Place]:
    """Return classified Wikipedia articles near the location, or [] on any failure."""
    try:
        response = await client.get(
            WIKIPEDIA_API,
            params={
                "action": "query",
                "format": "json",
                "generator": "geosearch",
                "ggscoord": f"{location.latitude}|{location.longitude}",
                "ggsradius": SEARCH_RADIUS_M,
                "ggslimit": 300,
                "prop": "description|coordinates",
                "colimit": 500,
            },
        )
        response.raise_for_status()
        pages = list(response.json().get("query", {}).get("pages", {}).values())
    except (httpx.HTTPError, ValueError):
        return []
    # Geosearch orders by distance; "index" preserves that order.
    pages.sort(key=lambda p: p.get("index", 0))
    return parse_pages(pages, interests)
