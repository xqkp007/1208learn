from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .settings import get_settings


settings = get_settings()

SOURCE_ENGINE = create_engine(
    settings.database.source_url,
    pool_pre_ping=True,
    pool_recycle=3600,
    future=True,
)
TARGET_ENGINE = create_engine(
    settings.database.target_url,
    pool_pre_ping=True,
    pool_recycle=3600,
    future=True,
)

SourceSessionLocal = sessionmaker(bind=SOURCE_ENGINE, autocommit=False, autoflush=False, expire_on_commit=False, future=True)
TargetSessionLocal = sessionmaker(bind=TARGET_ENGINE, autocommit=False, autoflush=False, expire_on_commit=False, future=True)


@contextmanager
def get_source_session() -> Session:
    session = SourceSessionLocal()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def get_target_session() -> Session:
    session = TargetSessionLocal()
    try:
        yield session
    finally:
        session.close()
