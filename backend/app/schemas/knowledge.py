from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question: str
    answer: str
    status: str
    updated_at: datetime = Field(..., serialization_alias="updatedAt")


class KnowledgeListResponse(BaseModel):
    total: int
    page: int
    pageSize: int
    items: List[KnowledgeItemOut]


class KnowledgeDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question: str
    answer: str
    status: str
    updated_at: datetime = Field(..., serialization_alias="updatedAt")


class KnowledgeUpdateRequest(BaseModel):
    question: Optional[str] = None
    answer: Optional[str] = None
    status: Optional[str] = None
