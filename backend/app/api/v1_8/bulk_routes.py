from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ...core.security import get_current_user
from ...models.user import User
from ...schemas.review import (
    BulkCreateKnowledgeItemsRequest,
    BulkCreateKnowledgeItemsResponse,
    BulkDiscardPendingFaqsRequest,
    BulkDiscardPendingFaqsResponse,
)
from ...services.review import NotFoundError, ReviewService
from ...services.scenario import ScenarioService


router = APIRouter(prefix="/api/v1.8", tags=["review-bulk"])
review_service = ReviewService()
scenario_service = ScenarioService()


@router.post(
    "/knowledge-items/bulk-create",
    response_model=BulkCreateKnowledgeItemsResponse,
    status_code=status.HTTP_201_CREATED,
)
def bulk_create_knowledge_items(
    body: BulkCreateKnowledgeItemsRequest,
    current_user: User = Depends(get_current_user),
) -> BulkCreateKnowledgeItemsResponse:
    try:
        scenario = scenario_service.get_scenario(current_user.scenario_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    payloads = [
        {
            "pending_faq_id": item.pending_faq_id,
            "scenario_id": item.scenario_id,
            "question": item.question,
            "answer": item.answer,
        }
        for item in body.items
    ]

    try:
        created_count = review_service.bulk_accept_pending_faqs(
            payloads=payloads,
            scenario_id=current_user.scenario_id,
            allowed_group_code=scenario.source_group_code,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return BulkCreateKnowledgeItemsResponse(createdCount=created_count)


@router.post(
    "/pending-faqs/bulk-discard",
    response_model=BulkDiscardPendingFaqsResponse,
)
def bulk_discard_pending_faqs(
    body: BulkDiscardPendingFaqsRequest,
    current_user: User = Depends(get_current_user),
) -> BulkDiscardPendingFaqsResponse:
    try:
        scenario = scenario_service.get_scenario(current_user.scenario_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    try:
        discarded_count = review_service.bulk_discard_pending_faqs(
            pending_faq_ids=body.pending_faq_ids,
            allowed_group_code=scenario.source_group_code,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return BulkDiscardPendingFaqsResponse(discardedCount=discarded_count)
