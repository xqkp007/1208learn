from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, func

from .base import Base


class Scenario(Base):
    __tablename__ = "scenarios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scenario_code = Column(String(50), nullable=False, unique=True)
    scenario_name = Column(String(100), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)

    # Optional mapping back to upstream/group codes, e.g. 'SW', 'GJ'
    source_group_code = Column(String(2), nullable=True)

    aico_username = Column(String(100), nullable=False)
    aico_user_id = Column(Integer, nullable=False)
    aico_project_name = Column(String(100), nullable=False)
    aico_kb_name = Column(String(100), nullable=False)

    aico_cached_pid = Column(Integer, nullable=True)
    aico_cached_kb_id = Column(Integer, nullable=True)
    aico_cached_token = Column(Text, nullable=True)
    aico_token_expires_at = Column(DateTime, nullable=True)

    sync_schedule = Column(String(50), nullable=False, default="0 2 * * *")

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
