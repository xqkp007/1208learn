from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.v1.routes import router as etl_router
from .api.v1_2.faq_routes import router as faq_router
from .api.v1_3.scenario_routes import router as scenario_router
from .api.v1_4.review_routes import router as review_router
from .api.v1_4_1.knowledge_routes import router as knowledge_router
from .api.v1_6.auth_routes import router as auth_router
from .api.v1_8 import router as review_bulk_router
from .api.v1_10 import router as admin_router
from .api.v1_12 import router as kb_taxonomy_router
from .api.v1_14 import router as kb_taxonomy_review_router
from .core.logging import configure_logging
from .core.settings import get_settings
from .jobs.scheduler import SchedulerManager


settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)
scheduler_manager = SchedulerManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler_manager.start()
    try:
        yield
    finally:
        scheduler_manager.shutdown()


app = FastAPI(title=settings.app_name, docs_url="/docs", redoc_url="/redoc", lifespan=lifespan)

def _parse_env_bool(key: str, default: bool) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_env_csv(key: str) -> list[str]:
    raw = os.getenv(key, "")
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


# CORS:
# - Dev defaults only allow the local Vite dev server.
# - In prod, set `CORS_ALLOW_ORIGINS` (comma-separated) to your frontend origins, e.g.
#   "https://app.example.com,http://app.example.com:5176"
_raw_cors_allow_origins = os.getenv("CORS_ALLOW_ORIGINS", "")
_raw_cors_allow_origin_regex = os.getenv("CORS_ALLOW_ORIGIN_REGEX", "")
_raw_cors_allow_credentials = os.getenv("CORS_ALLOW_CREDENTIALS", "")

origins = _parse_env_csv("CORS_ALLOW_ORIGINS") or [
    "http://127.0.0.1:5176",
    "http://localhost:5176",
]
origin_regex = os.getenv("CORS_ALLOW_ORIGIN_REGEX") or None
allow_credentials = _parse_env_bool("CORS_ALLOW_CREDENTIALS", default=True)

if _raw_cors_allow_origins.strip():
    logger.info("CORS config (env): CORS_ALLOW_ORIGINS=%s", _raw_cors_allow_origins)
else:
    logger.info("CORS config (default): allow_origins=%s", ",".join(origins))
if _raw_cors_allow_origin_regex.strip():
    logger.info("CORS config (env): CORS_ALLOW_ORIGIN_REGEX=%s", _raw_cors_allow_origin_regex)
if _raw_cors_allow_credentials.strip():
    logger.info("CORS config (env): CORS_ALLOW_CREDENTIALS=%s", _raw_cors_allow_credentials)
logger.info(
    "CORS config (effective): allow_origins=%s allow_origin_regex=%s allow_credentials=%s",
    origins,
    origin_regex,
    allow_credentials,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=origin_regex,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(etl_router)
app.include_router(faq_router)
app.include_router(scenario_router)
app.include_router(review_router)
app.include_router(knowledge_router)
app.include_router(auth_router)
app.include_router(review_bulk_router)
app.include_router(admin_router)
app.include_router(kb_taxonomy_router)
app.include_router(kb_taxonomy_review_router)


@app.get("/health", tags=["system"])
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
