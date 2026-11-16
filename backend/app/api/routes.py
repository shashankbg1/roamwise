"""HTTP endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.agents.service import plan_trip, refine_trip
from app.agents.state import Deps, Emit
from app.api.streaming import stream_job
from app.db.repository import TripRepository
from app.models.schemas import Itinerary, RefineRequest, TripRequest, TripSummary

router = APIRouter(prefix="/api")


def get_repo(request: Request) -> TripRepository:
    return request.app.state.repo


def _deps(request: Request, emit: Emit) -> Deps:
    state = request.app.state
    return Deps(
        llm=state.llm, http=state.http, emit=emit, max_revisions=state.settings.max_revisions
    )


@router.get("/health")
async def health(request: Request) -> dict[str, str]:
    return {"status": "ok", "llm_provider": request.app.state.llm.name}


@router.post("/trips", response_class=StreamingResponse)
async def create_trip(
    body: TripRequest, request: Request, repo: TripRepository = Depends(get_repo)
) -> StreamingResponse:
    """Plan a trip. The response is a stream of AgentEvent objects ending in `final` or `error`."""

    async def job(emit: Emit) -> Itinerary:
        itinerary, places = await plan_trip(body, _deps(request, emit))
        repo.save(itinerary, places)
        return itinerary

    return stream_job(job)


@router.post("/trips/{trip_id}/refine", response_class=StreamingResponse)
async def refine(
    trip_id: str,
    body: RefineRequest,
    request: Request,
    repo: TripRepository = Depends(get_repo),
) -> StreamingResponse:
    """Apply a follow-up request such as "make day 2 cheaper" to a saved trip."""
    found = repo.get(trip_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    itinerary, places = found

    async def job(emit: Emit) -> Itinerary:
        refined = await refine_trip(itinerary, places, body.message, _deps(request, emit))
        repo.save(refined, places)
        return refined

    return stream_job(job)


@router.get("/trips")
async def list_trips(repo: TripRepository = Depends(get_repo)) -> list[TripSummary]:
    return repo.list()


@router.get("/trips/{trip_id}")
async def get_trip(trip_id: str, repo: TripRepository = Depends(get_repo)) -> Itinerary:
    found = repo.get(trip_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    return found[0]


@router.delete("/trips/{trip_id}", status_code=204)
async def delete_trip(trip_id: str, repo: TripRepository = Depends(get_repo)) -> None:
    if not repo.delete(trip_id):
        raise HTTPException(status_code=404, detail="Trip not found")
