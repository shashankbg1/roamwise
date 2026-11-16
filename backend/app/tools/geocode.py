"""Turn a place name into coordinates using the Open-Meteo geocoding API (no key needed)."""

import httpx

from app.models.schemas import Location

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"


async def geocode(client: httpx.AsyncClient, name: str) -> Location | None:
    """Return the best match for `name`, or None when nothing is found."""
    response = await client.get(
        GEOCODE_URL, params={"name": name, "count": 1, "language": "en", "format": "json"}
    )
    response.raise_for_status()
    results = response.json().get("results") or []
    if not results:
        return None
    top = results[0]
    return Location(
        name=top["name"],
        country=top.get("country"),
        latitude=top["latitude"],
        longitude=top["longitude"],
        timezone=top.get("timezone"),
    )
