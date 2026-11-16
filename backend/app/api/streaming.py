"""Run an agent job in the background and stream its progress as server-sent events."""

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable

from fastapi.responses import StreamingResponse

from app.agents.state import Emit, TripError
from app.llm.base import LLMError
from app.models.schemas import AgentEvent, Itinerary

logger = logging.getLogger(__name__)

Job = Callable[[Emit], Awaitable[Itinerary]]


def _sse(event: AgentEvent) -> str:
    return f"data: {event.model_dump_json()}\n\n"


async def _events(job: Job) -> AsyncIterator[str]:
    queue: asyncio.Queue[AgentEvent | None] = asyncio.Queue()

    async def run() -> None:
        try:
            itinerary = await job(queue.put)
            await queue.put(
                AgentEvent(
                    type="final",
                    agent="system",
                    message="Your plan is ready",
                    data=itinerary.model_dump(mode="json"),
                )
            )
        except TripError as exc:
            await queue.put(AgentEvent(type="error", agent="system", message=str(exc)))
        except LLMError as exc:
            logger.warning("model backend failed: %s", exc)
            await queue.put(
                AgentEvent(
                    type="error",
                    agent="system",
                    message="The AI model couldn't complete this plan. Try again in a moment.",
                )
            )
        except Exception:
            logger.exception("trip job crashed")
            await queue.put(
                AgentEvent(
                    type="error",
                    agent="system",
                    message="Something went wrong while planning. Try again.",
                )
            )
        finally:
            await queue.put(None)

    task = asyncio.create_task(run())
    try:
        while (event := await queue.get()) is not None:
            yield _sse(event)
    finally:
        # If the browser disconnects mid-plan, stop the agents instead of working for nobody.
        task.cancel()


def stream_job(job: Job) -> StreamingResponse:
    return StreamingResponse(
        _events(job),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
