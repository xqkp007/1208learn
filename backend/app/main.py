from __future__ import annotations

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
scheduler_manager = SchedulerManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler_manager.start()
    try:
        yield
    finally:
        scheduler_manager.shutdown()


app = FastAPI(title=settings.app_name, docs_url="/docs", redoc_url="/redoc", lifespan=lifespan)

origins = [
    "http://127.0.0.1:5176",
    "http://localhost:5176",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
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
