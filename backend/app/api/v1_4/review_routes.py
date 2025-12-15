from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ...core.security import get_current_user
from ...core.logging import get_logger
from ...models.user import User
from ...schemas.review import (
    CreateKnowledgeItemRequest,
    CreateKnowledgeItemResponse,
    DiscardPendingFAQResponse,
    PendingFAQItem,
    PendingFAQListResponse,
)
from ...services.review import NotFoundError, ReviewService
from ...services.scenario import ScenarioService


logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1.4", tags=["review"])
review_service = ReviewService()
scenario_service = ScenarioService()


@router.get("/pending-faqs", response_model=PendingFAQListResponse)
def list_pending_faqs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    keyword: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
) -> PendingFAQListResponse:
    try:
        scenario = scenario_service.get_scenario(current_user.scenario_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    items, total = review_service.list_pending_faqs(
        page=page,
        page_size=page_size,
        keyword=keyword,
        source_group_code=scenario.source_group_code,
    )
    return PendingFAQListResponse(
        total=total,
        page=page,
        pageSize=page_size,
        items=[PendingFAQItem.from_orm(item) for item in items],
    )


@router.post(
    "/knowledge-items",
    response_model=CreateKnowledgeItemResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_knowledge_item(
    body: CreateKnowledgeItemRequest,
    current_user: User = Depends(get_current_user),
) -> CreateKnowledgeItemResponse:
    try:
        scenario = scenario_service.get_scenario(current_user.scenario_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    try:
        item = review_service.accept_pending_faq(
            pending_faq_id=body.pending_faq_id,
            scenario_id=body.scenario_id,
            question=body.question,
            answer=body.answer,
            allowed_group_code=scenario.source_group_code,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    return CreateKnowledgeItemResponse(id=item.id, status=item.status)


@router.delete("/pending-faqs/{pending_faq_id}", response_model=DiscardPendingFAQResponse)
def discard_pending_faq(
    pending_faq_id: int,
    current_user: User = Depends(get_current_user),
) -> DiscardPendingFAQResponse:
    try:
        scenario = scenario_service.get_scenario(current_user.scenario_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    try:
        review_service.discard_pending_faq(pending_faq_id, allowed_group_code=scenario.source_group_code)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    return DiscardPendingFAQResponse(message=f"Pending FAQ with id {pending_faq_id} has been discarded.")
