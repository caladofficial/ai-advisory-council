"""FastAPI application entrypoint for AI Advisory Council."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    advisors,
    audit,
    debate,
    evaluation,
    investigations,
    judge,
    models,
    reports,
    research,
)
from app.config import get_settings
from app.database.session import init_db, session_scope
from app.models.catalog_importer import sync_model_registry


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    with session_scope() as db:
        sync_model_registry(db, include_ollama=True, include_hf=False)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="AI Advisory Council",
        version="1.0.0",
        description="Evidence-first 10-advisor debate & 1-judge feasibility intelligence platform",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(investigations.router)
    app.include_router(research.router)
    app.include_router(advisors.router)
    app.include_router(debate.router)
    app.include_router(judge.router)
    app.include_router(reports.router)
    app.include_router(models.router)
    app.include_router(evaluation.router)
    app.include_router(audit.router)

    @app.get("/health")
    def health():
        return {"status": "ok", "cost_policy": settings.cost_policy_mode}

    return app


app = create_app()
