from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class TriggerETLRequest(BaseModel):
    target_date: Optional[date] = Field(
        default=None,
        description="The date whose conversations should be processed. Defaults to yesterday.",
    )


class TriggerETLResponse(BaseModel):
    target_date: date
    groups_processed: int
    conversations_total: int
    inserted: int
    skipped_existing: int
