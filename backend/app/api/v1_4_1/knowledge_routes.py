from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ...core.security import get_current_user
from ...models.user import User
from ...schemas.knowledge import (
    KnowledgeDetailResponse,
    KnowledgeItemOut,
    KnowledgeListResponse,
    KnowledgeUpdateRequest,
)
from ...services.knowledge import KnowledgeService
from ...services.review import NotFoundError


router = APIRouter(prefix="/api/v1.4.1", tags=["knowledge"])
knowledge_service = KnowledgeService()


@router.get("/knowledge-items", response_model=KnowledgeListResponse)
def list_knowledge_items(
    status: str = Query("active", pattern="^(active|disabled)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    keyword: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
) -> KnowledgeListResponse:
    items, total = knowledge_service.list_items(
        scenario_id=current_user.scenario_id,
        status=status,
        page=page,
        page_size=page_size,
        keyword=keyword,
    )
    return KnowledgeListResponse(
        total=total,
        page=page,
        pageSize=page_size,
        items=[KnowledgeItemOut.from_orm(item) for item in items],
    )


@router.get("/knowledge-items/{item_id}", response_model=KnowledgeDetailResponse)
def get_knowledge_item(
    item_id: int,
    current_user: User = Depends(get_current_user),
) -> KnowledgeDetailResponse:
    try:
        item = knowledge_service.get_item(
            item_id=item_id,
            scenario_id=current_user.scenario_id,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return KnowledgeDetailResponse.from_orm(item)


@router.put("/knowledge-items/{item_id}", response_model=KnowledgeDetailResponse)
def update_knowledge_item(
    item_id: int,
    body: KnowledgeUpdateRequest,
    current_user: User = Depends(get_current_user),
) -> KnowledgeDetailResponse:
    try:
        item = knowledge_service.update_item(
            item_id=item_id,
            scenario_id=current_user.scenario_id,
            question=body.question,
            answer=body.answer,
            status=body.status,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return KnowledgeDetailResponse.from_orm(item)

