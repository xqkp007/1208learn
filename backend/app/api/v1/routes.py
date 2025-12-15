from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ...core.logging import get_logger
from ...schemas.etl import TriggerETLRequest, TriggerETLResponse
from ...services.dialog_etl import DialogETLService


router = APIRouter(prefix="/api/v1/etl", tags=["etl"])
logger = get_logger(__name__)
etl_service = DialogETLService()


@router.post("/run", response_model=TriggerETLResponse)
def run_etl(body: TriggerETLRequest) -> TriggerETLResponse:
    target_date = body.target_date or etl_service.default_target_date()
    try:
        result = etl_service.run_for_date(target_date)
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Manual ETL trigger failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"ETL failed: {exc}") from exc

    return TriggerETLResponse(
        target_date=result.target_date,
        groups_processed=result.groups_processed,
        conversations_total=result.conversations_total,
        inserted=result.inserted,
        skipped_existing=result.skipped_existing,
    )
