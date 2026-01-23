from __future__ import annotations

from typing import List

from pydantic import BaseModel, ConfigDict, Field


class KbTaxonomyReviewPathSegment(BaseModel):
    level: int
    name: str


class KbTaxonomyReviewCaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str


class KbTaxonomyReviewItemOut(BaseModel):
    id: int
    scope_code: str = Field(..., serialization_alias="scopeCode")
    path: List[KbTaxonomyReviewPathSegment]
    definition: str
    cases: List[KbTaxonomyReviewCaseOut]


class KbTaxonomyReviewListResponse(BaseModel):
    items: List[KbTaxonomyReviewItemOut]


class KbTaxonomyReviewAcceptRequest(BaseModel):
    scope: str
    l3_name: str = Field(..., alias="l3Name")
    definition: str
    cases: List[str]

    class Config:
        populate_by_name = True


class KbTaxonomyReviewActionResponse(BaseModel):
    message: str
