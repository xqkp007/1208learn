from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, func

from .base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=True)
    scenario_id = Column(Integer, nullable=False, comment="绑定的场景ID，对应scenarios表")
    role = Column(String(20), nullable=False, default="auditor")
    is_active = Column(Boolean, nullable=False, default=True)
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

