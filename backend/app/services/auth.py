from __future__ import annotations

from typing import Optional

from sqlalchemy import select

from ..core.db import TargetSessionLocal
from ..core.logging import get_logger
from ..core.security import create_access_token, verify_password
from ..models.scenario import Scenario
from ..models.user import User
from .review import NotFoundError


logger = get_logger(__name__)


class AuthenticationError(Exception):
    """Raised when username/password is invalid."""


class AuthService:
    def authenticate_user(self, username: str, password: str) -> User:
        with TargetSessionLocal() as session:
            stmt = select(User).where(User.username == username)
            user: Optional[User] = session.execute(stmt).scalar_one_or_none()

            if user is None:
                raise AuthenticationError("Invalid username or password")

            if not verify_password(password, user.password_hash):
                raise AuthenticationError("Invalid username or password")

            if not user.is_active:
                raise AuthenticationError("User is inactive")

            # detach from session
            session.expunge(user)

        return user

    def get_scenario(self, scenario_id: int) -> Scenario:
        with TargetSessionLocal() as session:
            scenario = session.get(Scenario, scenario_id)
            if scenario is None:
                raise NotFoundError(f"Scenario {scenario_id} not found")
            session.expunge(scenario)
        return scenario

    def login(self, username: str, password: str) -> tuple[str, User, Scenario]:
        user = self.authenticate_user(username, password)
        scenario = self.get_scenario(user.scenario_id)

        token_payload = {
            "userId": user.id,
            "username": user.username,
            "role": user.role,
            "scenarioId": user.scenario_id,
        }
        access_token = create_access_token(subject=token_payload)

        logger.info("User %s logged in for scenario %s", user.username, scenario.scenario_code)
        return access_token, user, scenario

