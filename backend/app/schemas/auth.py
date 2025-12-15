from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginUserInfo(BaseModel):
    id: int = Field(..., alias="userId")
    username: str
    full_name: Optional[str] = Field(None, alias="fullName")
    role: str
    scenario_id: int = Field(..., alias="scenarioId")

    class Config:
        populate_by_name = True


class LoginResponse(BaseModel):
    access_token: str = Field(..., alias="accessToken")
    token_type: str = Field("bearer", alias="tokenType")
    user: LoginUserInfo

    class Config:
        populate_by_name = True
