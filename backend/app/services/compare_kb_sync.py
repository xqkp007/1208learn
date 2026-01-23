from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import object_session

from ..core.db import TargetSessionLocal
from ..core.logging import get_logger
from ..models.faq_review import PendingFAQ
from ..models.scenario import Scenario
from .aico_sync import AicoSyncError, AicoSyncOrchestrator, SyncRunResult


logger = get_logger(__name__)

COMPARE_SUFFIXES = ("_compare", "_compare_test")


@dataclass
class CompareSyncTask:
    scenario: Scenario
    aico_scenario: Scenario
    items: list[PendingFAQ]


class CompareKbSyncService:
    def __init__(self) -> None:
        self.orchestrator = AicoSyncOrchestrator()

    def run(self) -> List[SyncRunResult]:
        tasks = self._collect_tasks()
        results: list[SyncRunResult] = []
        for task in tasks:
            run_id = f"compare-{task.scenario.id}-{uuid.uuid4().hex[:8]}"
            try:
                result = self.orchestrator.run_for_items(
                    scenario=task.scenario,
                    aico_scenario=task.aico_scenario,
                    items=task.items,
                    run_id=run_id,
                    allow_empty=True,
                    source_label="pending FAQs",
                    skip_message="No pending FAQs to sync.",
                )
                results.append(result)
            except AicoSyncError as exc:
                logger.exception(
                    "Compare KB sync failed (scenario_id=%s, scenario_code=%s): %s",
                    task.scenario.id,
                    task.scenario.scenario_code,
                    exc,
                )
                results.append(
                    SyncRunResult(
                        scenario_id=task.scenario.id,
                        items=len(task.items),
                        status="failed",
                        message=str(exc),
                    )
                )

        return results

    def _collect_tasks(self) -> list[CompareSyncTask]:
        tasks: list[CompareSyncTask] = []
        with TargetSessionLocal() as session:
            def _safe_expunge(obj: object) -> None:
                if object_session(obj) is session:
                    session.expunge(obj)

            scenarios = (
                session.execute(select(Scenario).where(Scenario.is_active.is_(True)))
                .scalars()
                .all()
            )
            for scenario in scenarios:
                code = (scenario.scenario_code or "").strip()
                if not code or not code.endswith(COMPARE_SUFFIXES):
                    continue
                if not scenario.source_group_code:
                    logger.warning(
                        "Compare scenario missing source_group_code (scenario_id=%s code=%s)",
                        scenario.id,
                        scenario.scenario_code,
                    )
                    continue

                aico_scenario = self.orchestrator._select_aico_scenario(session, scenario)
                if aico_scenario.id != scenario.id:
                    logger.info(
                        "Skipping compare sync scenario_id=%s (scenario_code=%s); "
                        "current AICO host uses scenario_id=%s (scenario_code=%s)",
                        scenario.id,
                        scenario.scenario_code,
                        aico_scenario.id,
                        aico_scenario.scenario_code,
                    )
                    continue

                items = (
                    session.execute(
                        select(PendingFAQ).where(
                            PendingFAQ.status == "pending",
                            PendingFAQ.source_group_code == scenario.source_group_code,
                        )
                    )
                    .scalars()
                    .all()
                )

                _safe_expunge(scenario)
                if aico_scenario is not scenario:
                    _safe_expunge(aico_scenario)
                for item in items:
                    _safe_expunge(item)

                logger.info(
                    "Collected compare sync task (scenario_id=%s code=%s group=%s items=%d)",
                    scenario.id,
                    scenario.scenario_code,
                    scenario.source_group_code,
                    len(items),
                )
                tasks.append(
                    CompareSyncTask(
                        scenario=scenario,
                        aico_scenario=aico_scenario,
                        items=items,
                    )
                )

        return tasks
