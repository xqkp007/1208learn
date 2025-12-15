from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class PendingFAQItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question: str
    answer: str
    source_conversation_text: Optional[str] = None


class PendingFAQListResponse(BaseModel):
    total: int
    page: int
    pageSize: int
    items: List[PendingFAQItem]


class CreateKnowledgeItemRequest(BaseModel):
    pending_faq_id: int = Field(..., alias="pendingFaqId")
    scenario_id: int = Field(..., alias="scenarioId")
    question: str
    answer: str

    class Config:
        populate_by_name = True


class CreateKnowledgeItemResponse(BaseModel):
    id: int
    status: str


class DiscardPendingFAQResponse(BaseModel):
    message: str


class BulkCreateKnowledgeItemPayload(BaseModel):
    pending_faq_id: int = Field(..., alias="pendingFaqId")
    scenario_id: int = Field(..., alias="scenarioId")
    question: str
    answer: str

    class Config:
        populate_by_name = True


class BulkCreateKnowledgeItemsRequest(BaseModel):
    items: List[BulkCreateKnowledgeItemPayload]


class BulkCreateKnowledgeItemsResponse(BaseModel):
    createdCount: int


class BulkDiscardPendingFaqsRequest(BaseModel):
    pending_faq_ids: List[int] = Field(..., alias="pendingFaqIds")

    class Config:
        populate_by_name = True


class BulkDiscardPendingFaqsResponse(BaseModel):
    discardedCount: int
