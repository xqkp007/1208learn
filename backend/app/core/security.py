from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .db import TargetSessionLocal
from .logging import get_logger
from .settings import get_settings
from ..models.user import User
from ..services.review import NotFoundError


logger = get_logger(__name__)
settings = get_settings()
http_bearer = HTTPBearer(auto_error=False)


def hash_password(plain_password: str) -> str:
    """Hash a plain text password using SHA-256."""
    import hashlib

    return hashlib.sha256(plain_password.encode("utf-8")).hexdigest()


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    return hash_password(plain_password) == password_hash


def create_access_token(
    *, subject: Dict[str, Any], expires_minutes: Optional[int] = None
) -> str:
    auth_settings = settings.auth
    if expires_minutes is None:
        expires_minutes = auth_settings.access_token_expires_minutes

    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=expires_minutes)
    payload: Dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    token = jwt.encode(payload, auth_settings.secret_key, algorithm=auth_settings.algorithm)
    return token


def _get_user_by_id(user_id: int) -> User:
    with TargetSessionLocal() as session:
        user = session.get(User, user_id)
        if user is None:
            raise NotFoundError(f"User {user_id} not found")
        return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            settings.auth.secret_key,
            algorithms=[settings.auth.algorithm],
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        ) from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        ) from exc

    sub = payload.get("sub")
    if not isinstance(sub, dict):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    user_id = sub.get("userId")
    if not isinstance(user_id, int):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject",
        )

    try:
        user = _get_user_by_id(user_id)
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        ) from exc

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )

    return user
