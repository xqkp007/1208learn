from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, Integer, String, Text, func

from .base import Base


class PendingFAQ(Base):
    __tablename__ = "pending_faqs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    question = Column(Text, nullable=False, comment="AI提取的原始问题")
    answer = Column(Text, nullable=False, comment="AI提取的原始答案")
    status = Column(String(20), nullable=False, default="pending", comment="状态: pending, processed, discarded")
    source_group_code = Column(String(2), nullable=True, comment="来源场景编码")
    source_call_id = Column(String(64), nullable=True, comment="来源对话的call_id")
    source_conversation_text = Column(Text, nullable=True, comment="聚合后的原始对话全文")
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        default=datetime.utcnow,
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        default=datetime.utcnow,
        onupdate=func.now(),
    )


class KnowledgeItem(Base):
    __tablename__ = "knowledge_items"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="唯一主键")
    scenario_id = Column(Integer, nullable=False, index=True, comment="所属场景ID，对应scenarios表")
    question = Column(Text, nullable=False, comment="审核通过后的标准问题")
    answer = Column(Text, nullable=False, comment="审核通过后的标准答案")
    status = Column(String(20), nullable=False, default="active", comment="状态: active, disabled")
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        default=datetime.utcnow,
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        default=datetime.utcnow,
        onupdate=func.now(),
    )

