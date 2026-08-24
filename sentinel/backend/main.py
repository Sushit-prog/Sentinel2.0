"""SENTINEL API - evidence-grounded fraud intelligence.

Every analytical claim returned by this service carries citations,
calibrated confidence and a persisted audit trail.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.middleware import (
    ApiKeyMiddleware,
    RateLimitMiddleware,
    RequestContextMiddleware,
)
from backend.api.scamwatch import router as scamwatch_router
from backend.core.config import get_settings
from backend.core.logging import configure_logging
from backend.db.base import init_db

settings = get_settings()
configure_logging(level=settings.log_level, json_logs=settings.log_json)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    logger.info(
        "sentinel api started env=%s models=%s",
        settings.app_env,
        {"strong": settings.llm_strong_model, "fast": settings.llm_fast_model},
    )
    yield


app = FastAPI(
    title="SENTINEL API",
    version="2.0",
    description=(
        "Evidence-grounded fraud investigation API. Scam triage with "
        "quarantined extraction, cited verdicts, verification sampling and "
        "a deterministic emission policy."
    ),
    lifespan=lifespan,
)

app.add_middleware(RateLimitMiddleware)
app.add_middleware(ApiKeyMiddleware)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Key", "X-Request-ID", "Content-Type"],
    expose_headers=["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining"],
)

app.include_router(scamwatch_router, prefix="/api/scamwatch", tags=["SCAMWatch"])


@app.get("/", tags=["System"])
def root():
    return {"service": "sentinel", "version": "2.0", "status": "operational"}


@app.get("/health", tags=["System"])
def health():
    return {"status": "healthy", "version": "2.0"}
