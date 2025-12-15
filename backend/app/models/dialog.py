from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import BigInteger, Column, DateTime, Integer, String, Text, UniqueConstraint, func

from .base import Base


class ConversationStatus(str, Enum):
    UNPROCESSED = "unprocessed"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PROCESSED_NO_FAQ = "processed_no_faq"


class PeopleCustomerDialog(Base):
    __tablename__ = "people_customer_dialog"

    id = Column(BigInteger, primary_key=True)
    group_code = Column(String(4), nullable=False)
    call_id = Column(String(64), nullable=False)
    text = Column(Text, nullable=False)
    source = Column(Integer, nullable=False)  # 1=市民, 2=客服
    seq = Column(Integer)
    create_time = Column(DateTime, nullable=False)


class PreparedConversation(Base):
    __tablename__ = "prepared_conversations"
    __table_args__ = (UniqueConstraint("call_id", name="uk_call_id"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    group_code = Column(String(4), nullable=False)
    call_id = Column(String(64), nullable=False)
    full_text = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default=ConversationStatus.UNPROCESSED.value)
    conversation_time = Column(DateTime)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), default=datetime.utcnow)
