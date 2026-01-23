from __future__ import annotations

from typing import List, Set

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ...core.security import get_current_user
from ...models.user import User
from ...schemas.kb_taxonomy_review import (
    KbTaxonomyReviewAcceptRequest,
    KbTaxonomyReviewActionResponse,
    KbTaxonomyReviewCaseOut,
    KbTaxonomyReviewItemOut,
    KbTaxonomyReviewListResponse,
    KbTaxonomyReviewPathSegment,
)
from ...services.kb_taxonomy_review import KbTaxonomyReviewService, NotFoundError, ValidationError


router = APIRouter(prefix="/api/v1.14/kb-taxonomy-review", tags=["kb-taxonomy-review"])
service = KbTaxonomyReviewService()


def _allowed_scopes(user: User) -> Set[str]:
    if user.scenario_id == 2:
        return {"bus", "bike"}
    return {"water"}


def _require_scope(user: User, scope: str) -> str:
    if scope not in {"water", "bus", "bike"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid scope")
    allowed = _allowed_scopes(user)
    if scope not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Scope not allowed")
    return scope


@router.get("/pending", response_model=KbTaxonomyReviewListResponse)
def list_pending_review_items(
    scope: str = Query(...),
    current_user: User = Depends(get_current_user),
) -> KbTaxonomyReviewListResponse:
    scope = _require_scope(current_user, scope)
    items, case_map = service.list_pending(scope)

    response_items: List[KbTaxonomyReviewItemOut] = []
    for item in items:
        path = [
            KbTaxonomyReviewPathSegment(level=1, name=item.l1_name),
            KbTaxonomyReviewPathSegment(level=2, name=item.l2_name),
            KbTaxonomyReviewPathSegment(level=3, name=item.l3_name),
        ]
        cases = [KbTaxonomyReviewCaseOut.from_orm(c) for c in case_map.get(int(item.id), [])]
        response_items.append(
            KbTaxonomyReviewItemOut(
                id=int(item.id),
                scope_code=item.scope_code,
                path=path,
                definition=item.definition,
                cases=cases,
            )
        )

    return KbTaxonomyReviewListResponse(items=response_items)


@router.post(
    "/items/{review_item_id}/accept",
    response_model=KbTaxonomyReviewActionResponse,
    status_code=status.HTTP_200_OK,
)
def accept_review_item(
    review_item_id: int,
    body: KbTaxonomyReviewAcceptRequest,
    current_user: User = Depends(get_current_user),
) -> KbTaxonomyReviewActionResponse:
    scope = _require_scope(current_user, body.scope)
    try:
        service.accept_review_item(
            review_item_id=review_item_id,
            scope=scope,
            l3_name=body.l3_name,
            definition=body.definition,
            cases=body.cases,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    return KbTaxonomyReviewActionResponse(message="accepted")


@router.post(
    "/items/{review_item_id}/discard",
    response_model=KbTaxonomyReviewActionResponse,
    status_code=status.HTTP_200_OK,
)
def discard_review_item(
    review_item_id: int,
    scope: str = Query(...),
    current_user: User = Depends(get_current_user),
) -> KbTaxonomyReviewActionResponse:
    scope = _require_scope(current_user, scope)
    try:
        service.discard_review_item(review_item_id=review_item_id, scope=scope)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    return KbTaxonomyReviewActionResponse(message="discarded")
