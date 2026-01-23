from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, SmallInteger, String, Text, func

from .base import Base


class KbTaxonomyNode(Base):
    __tablename__ = "kb_taxonomy_nodes"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    scope_code = Column(String(16), nullable=False, index=True, comment="water|bus|bike")
    level = Column(SmallInteger, nullable=False, comment="1|2|3")
    name = Column(String(128), nullable=False)
    parent_id = Column(BigInteger, ForeignKey("kb_taxonomy_nodes.id"), nullable=True)
    definition = Column(Text, nullable=True, comment="Only level=3")
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


class KbTaxonomyCase(Base):
    __tablename__ = "kb_taxonomy_cases"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    node_id = Column(
        BigInteger,
        ForeignKey("kb_taxonomy_nodes.id", ondelete="CASCADE"),
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

