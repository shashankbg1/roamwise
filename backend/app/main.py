"""FastAPI entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import Settings, get_settings
from app.db.repository import TripRepository
from app.llm import build_provider

# Public data services ask clients to identify themselves.
USER_AGENT = "roamwise/0.1 (trip planner; https://github.com/shashankbg1/roamwise)"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings
        app.state.llm = build_provider(settings)
        app.state.repo = TripRepository(settings.db_path)
        async with httpx.AsyncClient(
            timeout=settings.http_timeout_seconds, headers={"User-Agent": USER_AGENT}
        ) as client:
            app.state.http = client
            yield

    app = FastAPI(title="Roamwise API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
