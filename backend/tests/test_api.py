"""API tests: real FastAPI app, mock model, faked network tools, temporary database."""

import json

import pytest
from fastapi.testclient import TestClient

from app.agents import nodes
from app.config import Settings
from app.main import create_app

BODY = {
    "destination": "Lisbon",
    "start_date": "2027-03-01",
    "end_date": "2027-03-03",
    "budget_usd": 600,
    "travelers": 2,
    "interests": ["history", "nature", "food"],
}


@pytest.fixture
def client(monkeypatch, tmp_path, location, places, weather):
    async def fake_geocode(http, name):
        return None if name == "Nowhereville" else location

    async def fake_weather(http, loc, start, end):
        return weather

    async def fake_places(http, loc, interests):
        return list(places)

    monkeypatch.setattr(nodes, "geocode", fake_geocode)
    monkeypatch.setattr(nodes, "get_weather", fake_weather)
    monkeypatch.setattr(nodes, "find_places", fake_places)
    settings = Settings(llm_provider="mock", db_path=str(tmp_path / "test.db"))
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def _stream(client, url, body) -> list[dict]:
    with client.stream("POST", url, json=body) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        return [json.loads(line[6:]) for line in response.iter_lines() if line.startswith("data: ")]


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok", "llm_provider": "mock"}


def test_plan_streams_progress_then_final_and_saves(client):
    events = _stream(client, "/api/trips", BODY)
    assert [e["agent"] for e in events if e["type"] == "agent_done"] == [
        "researcher",
        "planner",
        "budget",
        "critic",
    ]
    final = events[-1]
    assert final["type"] == "final" and len(final["data"]["days"]) == 3

    trip_id = final["data"]["id"]
    listed = client.get("/api/trips").json()
    assert [t["id"] for t in listed] == [trip_id] and listed[0]["destination"] == "Lisbon"
    assert client.get(f"/api/trips/{trip_id}").json()["id"] == trip_id


def test_refine_updates_the_saved_trip(client):
    trip = _stream(client, "/api/trips", BODY)[-1]["data"]
    events = _stream(client, f"/api/trips/{trip['id']}/refine", {"message": "make day 1 cheaper"})
    refined = events[-1]["data"]
    assert events[-1]["type"] == "final" and refined["id"] == trip["id"]
    assert refined["budget"]["total_estimated_usd"] < trip["budget"]["total_estimated_usd"]
    saved = client.get(f"/api/trips/{trip['id']}").json()
    assert saved["revisions"] == trip["revisions"] + 1
    assert len(client.get("/api/trips").json()) == 1


def test_unknown_destination_streams_an_error(client):
    events = _stream(client, "/api/trips", BODY | {"destination": "Nowhereville"})
    assert events[-1]["type"] == "error" and "Nowhereville" in events[-1]["message"]
    assert client.get("/api/trips").json() == []


def test_invalid_request_is_rejected(client):
    bad = BODY | {"end_date": "2027-02-01"}
    assert client.post("/api/trips", json=bad).status_code == 422


def test_missing_trip_returns_404(client):
    assert client.get("/api/trips/nope").status_code == 404
    assert client.post("/api/trips/nope/refine", json={"message": "cheaper"}).status_code == 404
    assert client.delete("/api/trips/nope").status_code == 404


def test_delete_removes_a_trip(client):
    trip_id = _stream(client, "/api/trips", BODY)[-1]["data"]["id"]
    assert client.delete(f"/api/trips/{trip_id}").status_code == 204
    assert client.get(f"/api/trips/{trip_id}").status_code == 404
