from __future__ import annotations

from typing import Dict, List, Optional, Set

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status

from ...core.security import get_current_user
from ...models.user import User
from ...schemas.kb_taxonomy import (
    KbTaxonomyCaseListResponse,
    KbTaxonomyCaseOut,
    KbTaxonomyCreateCaseRequest,
    KbTaxonomyCreateNodeRequest,
    KbTaxonomyImportSummary,
    KbTaxonomyImportValidateResponse,
    KbTaxonomyNodeDetail,
    KbTaxonomyPathSegment,
    KbTaxonomyTreeNode,
    KbTaxonomyTreeResponse,
    KbTaxonomyUpdateCaseRequest,
    KbTaxonomyUpdateNodeRequest,
)
from ...services.kb_taxonomy import KbTaxonomyService, NotFoundError, SCOPE_TO_DOMAIN_ZH, ValidationError


router = APIRouter(prefix="/api/v1.12/kb-taxonomy", tags=["kb-taxonomy"])
service = KbTaxonomyService()


def _allowed_scopes(user: User) -> Set[str]:
    # Keep consistent with current frontend mapping:
    # scenario_id==2: 公交（含公交/自行车 Tab），其他：水务
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


def _build_tree(nodes) -> List[KbTaxonomyTreeNode]:
    by_parent: Dict[Optional[int], List[KbTaxonomyTreeNode]] = {}
    for node in nodes:
        item = KbTaxonomyTreeNode(
            id=int(node.id),
            name=node.name,
            level=int(node.level),
            parent_id=int(node.parent_id) if node.parent_id is not None else None,
            children=[],
        )
        by_parent.setdefault(item.parent_id, []).append(item)

    for siblings in by_parent.values():
        siblings.sort(key=lambda x: (x.name, x.id))

    def attach(parent_id: Optional[int]) -> List[KbTaxonomyTreeNode]:
        children = by_parent.get(parent_id, [])
        for child in children:
            child.children = attach(child.id)
        return children

    return attach(None)


def _path_for_node(node_id: int) -> List[KbTaxonomyPathSegment]:
    segments: List[KbTaxonomyPathSegment] = []
    current_id: Optional[int] = node_id
    while current_id is not None:
        node = service.get_node(current_id)
        segments.append(KbTaxonomyPathSegment(id=int(node.id), name=node.name, level=int(node.level)))
        current_id = int(node.parent_id) if node.parent_id is not None else None
    segments.reverse()
    return segments


@router.get("/tree", response_model=KbTaxonomyTreeResponse)
def get_tree(
    scope: str = Query(...),
    current_user: User = Depends(get_current_user),
) -> KbTaxonomyTreeResponse:
    scope = _require_scope(current_user, scope)
    nodes = service.list_tree(scope)
    return KbTaxonomyTreeResponse(items=_build_tree(nodes))


@router.get("/nodes/{node_id}", response_model=KbTaxonomyNodeDetail)
def get_node_detail(
    node_id: int,
    scope: str = Query(...),
    current_user: User = Depends(get_current_user),
) -> KbTaxonomyNodeDetail:
    scope = _require_scope(current_user, scope)
    try:
        node = service.get_node(node_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if node.scope_code != scope:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")

    return KbTaxonomyNodeDetail(
        id=int(node.id),
        scope_code=node.scope_code,
        level=int(node.level),
        name=node.name,
        parent_id=int(node.parent_id) if node.parent_id is not None else None,
        definition=node.definition,
        path=_path_for_node(int(node.id)),
    )


@router.get("/nodes/{node_id}/cases", response_model=KbTaxonomyCaseListResponse)
def list_cases(
    node_id: int,
    scope: str = Query(...),
    keyword: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
) -> KbTaxonomyCaseListResponse:
    scope = _require_scope(current_user, scope)
    try:
        node = service.get_node(node_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if node.scope_code != scope:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")

    items = service.list_cases(node_id=node_id, keyword=keyword.strip() if keyword else None)
    return KbTaxonomyCaseListResponse(items=[KbTaxonomyCaseOut.from_orm(i) for i in items])


@router.post("/nodes", response_model=KbTaxonomyNodeDetail, status_code=status.HTTP_201_CREATED)
def create_node(
    body: KbTaxonomyCreateNodeRequest,
    current_user: User = Depends(get_current_user),
) -> KbTaxonomyNodeDetail:
    scope = _require_scope(current_user, body.scope)
    try:
        node = service.create_node(
            scope=scope,
            level=body.level,
            name=body.name,
            parent_id=body.parent_id,
            definition=body.definition,
        )
    except (ValidationError, NotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return KbTaxonomyNodeDetail(
        id=int(node.id),
        scope_code=node.scope_code,
        level=int(node.level),
        name=node.name,
        parent_id=int(node.parent_id) if node.parent_id is not None else None,
        definition=node.definition,
        path=_path_for_node(int(node.id)),
    )


@router.put("/nodes/{node_id}", response_model=KbTaxonomyNodeDetail)
def update_node(
    node_id: int,
    body: KbTaxonomyUpdateNodeRequest,
    current_user: User = Depends(get_current_user),
) -> KbTaxonomyNodeDetail:
    scope = _require_scope(current_user, body.scope)
    try:
        node = service.update_node(node_id=node_id, scope=scope, name=body.name, definition=body.definition)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return KbTaxonomyNodeDetail(
        id=int(node.id),
        scope_code=node.scope_code,
        level=int(node.level),
        name=node.name,
        parent_id=int(node.parent_id) if node.parent_id is not None else None,
        definition=node.definition,
        path=_path_for_node(int(node.id)),
    )


@router.delete("/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_node(
    node_id: int,
    scope: str = Query(...),
    current_user: User = Depends(get_current_user),
) -> Response:
    scope = _require_scope(current_user, scope)
    try:
        service.delete_node(node_id=node_id, scope=scope)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/cases", response_model=KbTaxonomyCaseOut, status_code=status.HTTP_201_CREATED)
def create_case(
    body: KbTaxonomyCreateCaseRequest,
    current_user: User = Depends(get_current_user),
) -> KbTaxonomyCaseOut:
    scope = _require_scope(current_user, body.scope)
    try:
        case = service.create_case(scope=scope, node_id=body.node_id, content=body.content)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return KbTaxonomyCaseOut.from_orm(case)


@router.put("/cases/{case_id}", response_model=KbTaxonomyCaseOut)
def update_case(
    case_id: int,
    body: KbTaxonomyUpdateCaseRequest,
    current_user: User = Depends(get_current_user),
) -> KbTaxonomyCaseOut:
    scope = _require_scope(current_user, body.scope)
    try:
        case = service.update_case(scope=scope, case_id=case_id, content=body.content)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return KbTaxonomyCaseOut.from_orm(case)


@router.delete("/cases/{case_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_case(
    case_id: int,
    scope: str = Query(...),
    current_user: User = Depends(get_current_user),
) -> Response:
    scope = _require_scope(current_user, scope)
    try:
        service.delete_case(scope=scope, case_id=case_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/import/validate", response_model=KbTaxonomyImportValidateResponse)
async def import_validate(
    scope: str = Query(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> KbTaxonomyImportValidateResponse:
    scope = _require_scope(current_user, scope)
    raw = await file.read()
    plan, errors = service.import_validate(scope=scope, raw=raw, filename=file.filename or "")
    if errors or plan is None:
        return KbTaxonomyImportValidateResponse(ok=False, errors=errors)
    return KbTaxonomyImportValidateResponse(
        ok=True,
        summary=KbTaxonomyImportSummary(categories=plan.category_count, cases=plan.case_count),
        errors=[],
    )


@router.post("/import/execute", response_model=KbTaxonomyImportValidateResponse)
async def import_execute(
    scope: str = Query(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> KbTaxonomyImportValidateResponse:
    scope = _require_scope(current_user, scope)
    raw = await file.read()
    plan, errors = service.import_validate(scope=scope, raw=raw, filename=file.filename or "")
    if errors or plan is None:
        return KbTaxonomyImportValidateResponse(ok=False, errors=errors)
    try:
        executed = service.import_execute(scope=scope, raw=raw, filename=file.filename or "")
    except ValidationError as exc:
        return KbTaxonomyImportValidateResponse(ok=False, errors=[{"row": 1, "column": "file", "message": str(exc)}])

    return KbTaxonomyImportValidateResponse(
        ok=True,
        summary=KbTaxonomyImportSummary(categories=executed.category_count, cases=executed.case_count),
        errors=[],
    )
