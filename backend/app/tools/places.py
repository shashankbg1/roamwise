"""Find points of interest near a destination.

Two free sources are queried at the same time: OpenStreetMap (through the Overpass API), which
knows restaurants, bars and parks, and Wikipedia, which knows the famous sights. Overpass is a
volunteer-run service that is sometimes slow or down, so it gets a short deadline and the
result degrades to Wikipedia alone instead of failing.
"""

import asyncio

import httpx

from app.models.schemas import Interest, Location, Place
from app.tools.wikipedia import find_places_wikipedia

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
SEARCH_RADIUS_M = 6000
PER_INTEREST_LIMIT = 40
OVERPASS_MIRROR_TIMEOUT_S = 6.0

# Overpass tag filters for each interest. Every filter also requires a name.
_FILTERS: dict[Interest, list[str]] = {
    Interest.HISTORY: [
        '["historic"~"^(castle|monument|ruins|memorial|archaeological_site|fort|palace)$"]',
        '["tourism"="museum"]',
    ],
    Interest.FOOD: ['["amenity"~"^(restaurant|cafe)$"]["cuisine"]', '["amenity"="marketplace"]'],
    Interest.NATURE: [
        '["leisure"~"^(park|garden|nature_reserve)$"]',
        '["tourism"="viewpoint"]',
        '["natural"="beach"]',
    ],
    Interest.ART: ['["tourism"~"^(gallery|museum)$"]', '["amenity"~"^(theatre|arts_centre)$"]'],
    Interest.NIGHTLIFE: ['["amenity"~"^(bar|pub|nightclub)$"]'],
    Interest.SHOPPING: ['["shop"~"^(mall|department_store)$"]', '["amenity"="marketplace"]'],
}

# Which tag keys decide a place's category, in priority order.
_CATEGORY_KEYS = ["historic", "tourism", "amenity", "leisure", "natural", "shop"]


def build_query(location: Location, interests: list[Interest]) -> str:
    around = f"(around:{SEARCH_RADIUS_M},{location.latitude},{location.longitude})"
    blocks = []
    for interest in interests:
        statements = "".join(f'nwr{f}["name"]{around};' for f in _FILTERS[interest])
        blocks.append(f"({statements});out center tags {PER_INTEREST_LIMIT};")
    return "[out:json][timeout:20];" + "".join(blocks)


def _category(tags: dict[str, str]) -> str:
    for key in _CATEGORY_KEYS:
        if key in tags:
            return tags[key]
    return "place"


def _interest_for(tags: dict[str, str], wanted: list[Interest]) -> Interest:
    """Pick which requested interest a place serves best."""
    amenity, tourism = tags.get("amenity", ""), tags.get("tourism", "")
    guesses: list[Interest] = []
    if "historic" in tags:
        guesses.append(Interest.HISTORY)
    if tourism == "museum":
        guesses += [Interest.HISTORY, Interest.ART]
    if tourism == "gallery" or amenity in {"theatre", "arts_centre"}:
        guesses.append(Interest.ART)
    if amenity in {"restaurant", "cafe"}:
        guesses.append(Interest.FOOD)
    if amenity == "marketplace":
        guesses += [Interest.FOOD, Interest.SHOPPING]
    if "leisure" in tags or "natural" in tags or tourism == "viewpoint":
        guesses.append(Interest.NATURE)
    if amenity in {"bar", "pub", "nightclub"}:
        guesses.append(Interest.NIGHTLIFE)
    if "shop" in tags:
        guesses.append(Interest.SHOPPING)
    for guess in guesses:
        if guess in wanted:
            return guess
    return guesses[0] if guesses else wanted[0]


def parse_elements(elements: list[dict], interests: list[Interest]) -> list[Place]:
    """Convert raw Overpass elements to Places: named, deduplicated, well-known ones first."""
    seen: set[str] = set()
    places: list[Place] = []
    for element in elements:
        tags = element.get("tags") or {}
        name = tags.get("name:en") or tags.get("name")
        center = element.get("center") or element
        lat, lon = center.get("lat"), center.get("lon")
        if not name or lat is None or lon is None or name.lower() in seen:
            continue
        seen.add(name.lower())
        places.append(
            Place(
                name=name,
                category=_category(tags),
                interest=_interest_for(tags, interests),
                latitude=lat,
                longitude=lon,
                notable="wikipedia" in tags or "wikidata" in tags,
                website=tags.get("website"),
            )
        )
    places.sort(key=lambda p: not p.notable)
    return places


async def find_places_overpass(
    client: httpx.AsyncClient, location: Location, interests: list[Interest]
) -> list[Place]:
    """Query Overpass, trying each mirror in turn. Returns [] if every mirror fails."""
    query = build_query(location, interests)
    for url in OVERPASS_URLS:
        try:
            response = await client.post(
                url, data={"data": query}, timeout=OVERPASS_MIRROR_TIMEOUT_S
            )
            response.raise_for_status()
            return parse_elements(response.json().get("elements", []), interests)
        except (httpx.HTTPError, ValueError):
            continue
    return []


def merge_places(*sources: list[Place]) -> list[Place]:
    """Combine sources, dropping duplicate names; well-known places come first."""
    seen: set[str] = set()
    merged: list[Place] = []
    for source in sources:
        for place in source:
            key = place.name.lower()
            if key not in seen:
                seen.add(key)
                merged.append(place)
    merged.sort(key=lambda p: not p.notable)
    return merged


async def find_places(
    client: httpx.AsyncClient, location: Location, interests: list[Interest]
) -> list[Place]:
    """Return places for the requested interests from Wikipedia and OpenStreetMap combined."""
    if not interests:
        return []
    wikipedia, overpass = await asyncio.gather(
        find_places_wikipedia(client, location, interests),
        find_places_overpass(client, location, interests),
    )
    return merge_places(wikipedia, overpass)
