from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ...core.logging import get_logger
from ...schemas.faq import TriggerFAQExtractionRequest, TriggerFAQExtractionResponse
from ...services.faq_extraction import FAQExtractionService


logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1.2/faq", tags=["faq-extraction"])
faq_service = FAQExtractionService()


@router.post("/run", response_model=TriggerFAQExtractionResponse)
def run_faq_extraction(body: TriggerFAQExtractionRequest) -> TriggerFAQExtractionResponse:
    try:
        result = faq_service.run(target_date=body.target_date)
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("FAQ extraction failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"FAQ extraction failed: {exc}") from exc

    return TriggerFAQExtractionResponse(
        target_date=result.target_date,
        conversations_total=result.conversations_total,
        faqs_created=result.faqs_created,
    )
