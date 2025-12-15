from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class TriggerFAQExtractionRequest(BaseModel):
    target_date: Optional[date] = Field(
        default=None,
        description="只处理该日期的对话（按 conversation_time）。不传则处理所有未处理的对话。",
    )


class TriggerFAQExtractionResponse(BaseModel):
    target_date: Optional[date]
    conversations_total: int
    faqs_created: int

