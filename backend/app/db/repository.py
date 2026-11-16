"""Saved trips, stored in SQLite.

Each trip is one row holding the itinerary as JSON, plus the places found during research so a
later refinement can reuse them without searching again. Callers depend on the methods here,
not on SQLite, so a DynamoDB version can replace this class when the app moves to AWS.
"""

import json
import sqlite3
from contextlib import closing

from app.models.schemas import Itinerary, Place, TripSummary

_SCHEMA = """
CREATE TABLE IF NOT EXISTS trips (
    id          TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL,
    itinerary   TEXT NOT NULL,
    places      TEXT NOT NULL
)
"""


class TripRepository:
    def __init__(self, path: str) -> None:
        self._path = path
        with closing(self._connect()) as conn, conn:
            conn.execute(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        # A connection per call keeps this safe to use from any thread.
        return sqlite3.connect(self._path)

    def save(self, itinerary: Itinerary, places: list[Place]) -> None:
        """Insert a trip, or replace it if the id already exists."""
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT OR REPLACE INTO trips (id, created_at, itinerary, places) "
                "VALUES (?, ?, ?, ?)",
                (
                    itinerary.id,
                    itinerary.created_at.isoformat(),
                    itinerary.model_dump_json(),
                    json.dumps([p.model_dump(mode="json") for p in places]),
                ),
            )

    def get(self, trip_id: str) -> tuple[Itinerary, list[Place]] | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT itinerary, places FROM trips WHERE id = ?", (trip_id,)
            ).fetchone()
        if row is None:
            return None
        itinerary = Itinerary.model_validate_json(row[0])
        places = [Place.model_validate(p) for p in json.loads(row[1])]
        return itinerary, places

    def list(self) -> list[TripSummary]:
        """All saved trips, newest first."""
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT itinerary FROM trips ORDER BY created_at DESC").fetchall()
        summaries = []
        for (raw,) in rows:
            trip = Itinerary.model_validate_json(raw)
            summaries.append(
                TripSummary(
                    id=trip.id,
                    destination=trip.location.name,
                    start_date=trip.request.start_date,
                    end_date=trip.request.end_date,
                    total_estimated_usd=trip.budget.total_estimated_usd,
                    created_at=trip.created_at,
                )
            )
        return summaries

    def delete(self, trip_id: str) -> bool:
        with closing(self._connect()) as conn, conn:
            return conn.execute("DELETE FROM trips WHERE id = ?", (trip_id,)).rowcount > 0
