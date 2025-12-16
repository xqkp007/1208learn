from __future__ import annotations

from typing import List, Tuple

from sqlalchemy import func, select

from ..core.db import TargetSessionLocal
from ..core.logging import get_logger
from ..models.scenario import Scenario
from .review import NotFoundError


logger = get_logger(__name__)


class ScenarioService:
    def list_scenarios(self) -> Tuple[List[Scenario], int]:
        with TargetSessionLocal() as session:
            total = session.execute(select(func.count()).select_from(Scenario)).scalar_one()
            items = session.execute(select(Scenario).order_by(Scenario.id.asc())).scalars().all()
        return items, total

    def create_scenario(
        self,
        *,
        scenario_code: str,
        scenario_name: str,
        is_active: bool,
        aico_username: str,
        aico_user_id: int,
        aico_project_name: str,
        aico_kb_name: str,
        aico_host: str | None = None,
        sync_schedule: str,
        source_group_code: str | None = None,
    ) -> Scenario:
        with TargetSessionLocal() as session:
            scenario = Scenario(
                scenario_code=scenario_code,
                scenario_name=scenario_name,
                is_active=is_active,
                aico_username=aico_username,
                aico_user_id=aico_user_id,
                aico_project_name=aico_project_name,
                aico_kb_name=aico_kb_name,
                aico_host=aico_host,
                source_group_code=source_group_code,
                sync_schedule=sync_schedule,
            )
            session.add(scenario)
            session.commit()
            session.refresh(scenario)

        logger.info("Created scenario %s (%s)", scenario.id, scenario.scenario_code)
        return scenario

    def get_scenario(self, scenario_id: int) -> Scenario:
        with TargetSessionLocal() as session:
            scenario = session.get(Scenario, scenario_id)
            if scenario is None:
                raise NotFoundError(f"Scenario {scenario_id} not found")
        return scenario

    def update_scenario(self, scenario_id: int, **fields) -> Scenario:
        with TargetSessionLocal() as session:
            scenario = session.get(Scenario, scenario_id)
            if scenario is None:
                raise NotFoundError(f"Scenario {scenario_id} not found")

            for key, value in fields.items():
                if value is not None and hasattr(scenario, key):
                    setattr(scenario, key, value)

            session.commit()
            session.refresh(scenario)

        logger.info("Updated scenario %s", scenario_id)
        return scenario
