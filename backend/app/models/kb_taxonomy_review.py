from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, Text, func

from .base import Base


class KbTaxonomyReviewItem(Base):
    __tablename__ = "kb_taxonomy_review_items"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    scope_code = Column(String(16), nullable=False, index=True, comment="water|bus|bike")
    l1_name = Column(String(128), nullable=False)
    l2_name = Column(String(128), nullable=False)
    l3_name = Column(String(128), nullable=False)
    definition = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="pending", comment="pending|accepted|discarded")
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


class KbTaxonomyReviewCase(Base):
    __tablename__ = "kb_taxonomy_review_cases"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    review_item_id = Column(
        BigInteger,
        ForeignKey("kb_taxonomy_review_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content = Column(Text, nullable=False)
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
