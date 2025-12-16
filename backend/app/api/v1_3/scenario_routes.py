from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from ...core.security import get_current_user
from ...core.logging import get_logger
from ...models.user import User
from ...schemas.scenario import (
    ScenarioCreate,
    ScenarioListResponse,
    ScenarioOut,
    ScenarioSyncResult,
    ScenarioUpdate,
)
from ...services.aico_sync import AicoSyncError, AicoSyncOrchestrator
from ...services.review import NotFoundError
from ...services.scenario import ScenarioService


logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1.3", tags=["scenarios"])
scenario_service = ScenarioService()
sync_orchestrator = AicoSyncOrchestrator()


@router.get("/scenarios", response_model=ScenarioListResponse)
def list_scenarios() -> ScenarioListResponse:
    items, total = scenario_service.list_scenarios()
    return ScenarioListResponse(
        total=total,
        items=[ScenarioOut.from_orm(item) for item in items],
    )


@router.post("/scenarios", response_model=ScenarioOut, status_code=status.HTTP_201_CREATED)
def create_scenario(body: ScenarioCreate) -> ScenarioOut:
    scenario = scenario_service.create_scenario(
        scenario_code=body.scenario_code,
        scenario_name=body.scenario_name,
        is_active=body.is_active,
        aico_username=body.aico_username,
        aico_user_id=body.aico_user_id,
        aico_project_name=body.aico_project_name,
        aico_kb_name=body.aico_kb_name,
        aico_host=body.aico_host,
        sync_schedule=body.sync_schedule,
    )
    return ScenarioOut.from_orm(scenario)


@router.put("/scenarios/{scenario_id}", response_model=ScenarioOut)
def update_scenario(scenario_id: int, body: ScenarioUpdate) -> ScenarioOut:
    try:
        scenario = scenario_service.update_scenario(
            scenario_id,
            scenario_name=body.scenario_name,
            is_active=body.is_active,
            aico_username=body.aico_username,
            aico_user_id=body.aico_user_id,
            aico_project_name=body.aico_project_name,
            aico_kb_name=body.aico_kb_name,
            aico_host=body.aico_host,
            sync_schedule=body.sync_schedule,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return ScenarioOut.from_orm(scenario)


@router.post("/scenarios/{scenario_id}/trigger-sync", response_model=ScenarioSyncResult)
def trigger_sync(
    scenario_id: int,
    current_user: User = Depends(get_current_user),
) -> ScenarioSyncResult:
    if scenario_id != current_user.scenario_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: scenario mismatch",
        )

    run_id = uuid4().hex[:8]
    logger.info("AICO sync requested (run_id=%s, scenario_id=%s, user_id=%s)", run_id, scenario_id, current_user.id)

    try:
        result = sync_orchestrator.run_for_scenario(scenario_id, run_id=run_id)
    except AicoSyncError as exc:
        logger.exception("AICO sync failed (run_id=%s, scenario_id=%s): %s", run_id, scenario_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"[run_id={run_id}] {exc}",
        ) from exc
    except Exception as exc:
        logger.exception("AICO sync crashed (run_id=%s, scenario_id=%s): %s", run_id, scenario_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"[run_id={run_id}] Unexpected error during sync.",
        ) from exc

    return ScenarioSyncResult(
        scenarioId=result.scenario_id,
        items=result.items,
        status=result.status,
        message=f"[run_id={run_id}] {result.message}",
    )
