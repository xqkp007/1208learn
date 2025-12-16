from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ScenarioBase(BaseModel):
    scenario_code: str
    scenario_name: str
    is_active: bool = True
    aico_username: str
    aico_user_id: int
    aico_project_name: str
    aico_kb_name: str
    aico_host: Optional[str] = Field(default=None, description="Bind this scenario config to a specific AICO_HOST")
    sync_schedule: str = Field(default="0 2 * * *", description="Cron expression in Unix format")


class ScenarioCreate(ScenarioBase):
    pass


class ScenarioUpdate(BaseModel):
    scenario_name: Optional[str] = None
    is_active: Optional[bool] = None
    aico_username: Optional[str] = None
    aico_user_id: Optional[int] = None
    aico_project_name: Optional[str] = None
    aico_kb_name: Optional[str] = None
    aico_host: Optional[str] = None
    sync_schedule: Optional[str] = None


class ScenarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scenario_code: str
    scenario_name: str
    is_active: bool
    aico_username: str
    aico_user_id: int
    aico_project_name: str
    aico_kb_name: str
    aico_host: Optional[str] = None
    aico_cached_pid: Optional[int] = None
    aico_cached_kb_id: Optional[int] = None
    aico_cached_token: Optional[str] = None
    aico_token_expires_at: Optional[datetime] = None
    sync_schedule: str


class ScenarioListResponse(BaseModel):
    total: int
    items: List[ScenarioOut]


class ScenarioSyncResult(BaseModel):
    scenario_id: int = Field(..., alias="scenarioId")
    items: int
    status: str
    message: str
