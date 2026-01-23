from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class KbTaxonomyTreeNode(BaseModel):
    id: int
    name: str
    level: int
    parent_id: Optional[int] = Field(default=None, serialization_alias="parentId")
    children: List["KbTaxonomyTreeNode"] = Field(default_factory=list)


KbTaxonomyTreeNode.model_rebuild()


class KbTaxonomyPathSegment(BaseModel):
    id: int
    name: str
    level: int


class KbTaxonomyNodeDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scope_code: str = Field(..., serialization_alias="scopeCode")
    level: int
    name: str
    parent_id: Optional[int] = Field(default=None, serialization_alias="parentId")
    definition: Optional[str] = None
    path: List[KbTaxonomyPathSegment]


class KbTaxonomyCaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    node_id: int = Field(..., serialization_alias="nodeId")
    content: str


class KbTaxonomyCaseListResponse(BaseModel):
    items: List[KbTaxonomyCaseOut]


class KbTaxonomyTreeResponse(BaseModel):
    items: List[KbTaxonomyTreeNode]


class KbTaxonomyCreateNodeRequest(BaseModel):
    scope: str
    parent_id: Optional[int] = Field(default=None, alias="parentId")
    level: int
    name: str
    definition: Optional[str] = None

    class Config:
        populate_by_name = True


class KbTaxonomyUpdateNodeRequest(BaseModel):
    scope: str
    name: Optional[str] = None
    definition: Optional[str] = None

    class Config:
        populate_by_name = True


class KbTaxonomyCreateCaseRequest(BaseModel):
    scope: str
    node_id: int = Field(..., alias="nodeId")
    content: str

    class Config:
        populate_by_name = True


class KbTaxonomyUpdateCaseRequest(BaseModel):
    scope: str
    content: str

    class Config:
        populate_by_name = True


class KbTaxonomyImportError(BaseModel):
    row: int
    column: str
    message: str
    expected: Optional[str] = None
    actual: Optional[str] = None


class KbTaxonomyImportSummary(BaseModel):
    categories: int
    cases: int


class KbTaxonomyImportValidateResponse(BaseModel):
    ok: bool
    summary: Optional[KbTaxonomyImportSummary] = None
    errors: List[KbTaxonomyImportError] = Field(default_factory=list)
