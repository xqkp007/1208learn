from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from ...core.logging import get_logger
from ...schemas.auth import LoginRequest, LoginResponse, LoginUserInfo
from ...services.auth import AuthService, AuthenticationError


logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1.6", tags=["auth"])
auth_service = AuthService()


@router.post("/auth/login", response_model=LoginResponse)
def login(body: LoginRequest) -> LoginResponse:
    try:
        access_token, user, scenario = auth_service.login(body.username, body.password)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Login failed for user %s", body.username)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from exc

    user_info = LoginUserInfo(
        userId=user.id,
        username=user.username,
        fullName=user.full_name,
        role=user.role,
        scenarioId=user.scenario_id,
    )

    return LoginResponse(
        accessToken=access_token,
        tokenType="bearer",
        user=user_info,
    )

