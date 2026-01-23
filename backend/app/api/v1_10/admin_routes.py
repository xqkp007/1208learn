from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ...core.logging import get_logger
from ...core.security import get_current_user
from ...core.settings import get_settings
from ...models.user import User
from ...services.compare_kb_sync import CompareKbSyncService
from ...services.dialog_etl import DialogETLService
from ...services.faq_extraction import FAQExtractionService


logger = get_logger(__name__)
settings = get_settings()
router = APIRouter(prefix="/api/v1.10/admin", tags=["admin"])

etl_service = DialogETLService()
faq_service = FAQExtractionService()
compare_sync_service = CompareKbSyncService()


class TriggerAggregationRequest(BaseModel):
    start_time: datetime = Field(..., alias="startTime")
    end_time: datetime = Field(..., alias="endTime")


class TriggerExtractionRequest(BaseModel):
    limit: Optional[int] = Field(default=None, ge=1, le=1000)


class TriggerJobResponse(BaseModel):
    job_id: str = Field(..., alias="jobId")
    message: str


def _coerce_range_to_dates(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    """
    Normalize datetime range into the app timezone and snap to whole days [00:00, 24:00).
    """
    tz_name = settings.scheduler.timezone
    try:
        import zoneinfo

        tz = zoneinfo.ZoneInfo(tz_name)
    except Exception:  # pragma: no cover - fallback
        tz = None

    if start.tzinfo is not None and tz is not None:
        start = start.astimezone(tz)
    if end.tzinfo is not None and tz is not None:
        end = end.astimezone(tz)

    if start > end:
        raise ValueError("startTime must be <= endTime")

    start_day = datetime.combine(start.date(), datetime.min.time())
    end_day_exclusive = datetime.combine(end.date(), datetime.min.time()) + timedelta(days=1)
    return start_day, end_day_exclusive


def _run_aggregation_job(job_id: str, start_time: datetime, end_time: datetime) -> None:
    logger.info("Admin aggregation job %s started: %s -> %s", job_id, start_time, end_time)
    current = start_time.date()
    last = (end_time - timedelta(microseconds=1)).date()
    while current <= last:
        etl_service.run_for_date(current)
        current += timedelta(days=1)
    logger.info("Admin aggregation job %s completed", job_id)


def _run_extraction_job(job_id: str, limit: Optional[int]) -> None:
    logger.info("Admin extraction job %s started (limit=%s)", job_id, limit)
    faq_service.run(limit=limit)
    compare_sync_service.run()
    logger.info("Admin extraction job %s completed", job_id)


def _run_compare_kb_sync_job(job_id: str) -> None:
    logger.info("Admin compare KB sync job %s started", job_id)
    compare_sync_service.run()
    logger.info("Admin compare KB sync job %s completed", job_id)


@router.post(
    "/trigger-aggregation",
    response_model=TriggerJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def trigger_aggregation(
    body: TriggerAggregationRequest,
    current_user: User = Depends(get_current_user),
) -> TriggerJobResponse:
    _ = current_user  # login-only gate, no RBAC in v1.10
    try:
        start_time, end_time = _coerce_range_to_dates(body.start_time, body.end_time)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    job_id = f"agg-{uuid.uuid4().hex}"
    thread = threading.Thread(
        target=_run_aggregation_job,
        args=(job_id, start_time, end_time),
        daemon=True,
    )
    thread.start()

    return TriggerJobResponse(
        jobId=job_id,
        message="Aggregation task triggered.",
    )


@router.post(
    "/trigger-extraction",
    response_model=TriggerJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def trigger_extraction(
    body: TriggerExtractionRequest = Body(default_factory=TriggerExtractionRequest),
    current_user: User = Depends(get_current_user),
) -> TriggerJobResponse:
    _ = current_user  # login-only gate, no RBAC in v1.10
    job_id = f"ext-{uuid.uuid4().hex}"
    thread = threading.Thread(
        target=_run_extraction_job,
        args=(job_id, body.limit),
        daemon=True,
    )
    thread.start()

    return TriggerJobResponse(
        jobId=job_id,
        message="Extraction task triggered.",
    )


@router.post(
    "/trigger-compare-kb-sync",
    response_model=TriggerJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def trigger_compare_kb_sync(
    current_user: User = Depends(get_current_user),
) -> TriggerJobResponse:
    _ = current_user  # login-only gate, no RBAC in v1.10
    job_id = f"compare-sync-{uuid.uuid4().hex}"
    thread = threading.Thread(
        target=_run_compare_kb_sync_job,
        args=(job_id,),
        daemon=True,
    )
    thread.start()

    return TriggerJobResponse(
        jobId=job_id,
        message="Compare KB sync task triggered.",
    )
