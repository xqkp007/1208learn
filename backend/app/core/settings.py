from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import parse_qsl, urlparse

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from sqlalchemy.engine import URL


BASE_DIR = Path(__file__).resolve().parents[3]
ENV_FILE = BASE_DIR / ".env"


def _load_nonstandard_env_file(path: Path) -> None:
    """
    The existing .env file uses `key: value` pairs instead of `key=value`.
    This helper normalizes those entries so python-dotenv and os.environ can consume them.
    """
    if not path.exists():
        return

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if key and value:
                if key not in os.environ:
                    os.environ[key] = value
                key_upper = key.upper()
                if key_upper not in os.environ:
                    os.environ[key_upper] = value
            continue
        if "=" in line:
            # python-dotenv will process it.
            continue


if ENV_FILE.exists():
    _load_nonstandard_env_file(ENV_FILE)
    load_dotenv(ENV_FILE)


def _get_env_value(*keys: str, default: Optional[str] = None) -> Optional[str]:
    for key in keys:
        value = os.getenv(key)
        if value:
            return value.strip()
    return default


def _normalize_mysql_url(raw_url: str, username: Optional[str], password: Optional[str]) -> str:
    if raw_url.startswith("jdbc:"):
        raw_url = raw_url.replace("jdbc:", "", 1)
    if raw_url.startswith("mysql+mysqldb://"):
        raw_url = raw_url.replace("mysql+mysqldb://", "mysql+pymysql://", 1)
    elif raw_url.startswith("mysql://"):
        raw_url = raw_url.replace("mysql://", "mysql+pymysql://", 1)

    parsed = urlparse(raw_url)

    final_username = parsed.username or username
    final_password = parsed.password or password
    if final_username is None or final_password is None:
        raise ValueError(
            "Database credentials are required. Provide username/password via environment variables."
        )

    query: Dict[str, str] = _sanitize_mysql_query_params(dict(parse_qsl(parsed.query)))
    database = parsed.path.lstrip("/") if parsed.path else None
    if not database:
        raise ValueError("Database name missing in JDBC URL.")

    url_object = URL.create(
        drivername="mysql+pymysql",
        username=final_username,
        password=final_password,
        host=parsed.hostname or "localhost",
        port=parsed.port or 3306,
        database=database,
        query=query or None,
    )
    # Important: do not hide the password in the returned URL string,
    # otherwise SQLAlchemy will see '***' instead of the real password.
    return url_object.render_as_string(hide_password=False)


def _sanitize_mysql_query_params(params: Dict[str, str]) -> Dict[str, str]:
    sanitized: Dict[str, str] = {}
    truthy = {"1", "true", "yes", "on"}
    for key, value in params.items():
        normalized = key.strip()
        if not normalized:
            continue
        lower_key = normalized.lower()
        cleaned_value = value.strip()

        if lower_key == "characterencoding":
            if cleaned_value:
                sanitized["charset"] = cleaned_value
            continue
        if lower_key == "useunicode":
            # pymysql already uses unicode; ignore the hint
            continue
        if lower_key == "usessl":
            if cleaned_value.lower() in truthy:
                sanitized["ssl"] = "1"
            continue
        if lower_key == "servertimezone":
            tz = cleaned_value.replace("'", "")
            if tz:
                sanitized["init_command"] = f"SET time_zone = '{tz}'"
            continue

        # Preserve snake_case keys, drop CamelCase ones to avoid pymysql errors.
        if any(ch.isupper() for ch in normalized):
            continue

        sanitized[normalized] = cleaned_value

    return sanitized


def _resolve_database_url(prefix: Optional[str] = None, fallback: Optional[str] = None) -> str:
    prefix = prefix or ""
    normalized_prefix = prefix.upper()
    url = _get_env_value(
        f"{normalized_prefix}DATABASE_URL",
        f"{normalized_prefix}DB_URL",
        f"{normalized_prefix}SQLALCHEMY_DATABASE_URI",
        f"{normalized_prefix}URL",
        default=fallback,
    )
    if not url:
        raise ValueError(
            f"Database URL not provided for prefix '{prefix}'. "
            f"Set {normalized_prefix}DATABASE_URL or URL in the .env file."
        )

    username = _get_env_value(
        f"{normalized_prefix}DATABASE_USERNAME",
        f"{normalized_prefix}DB_USERNAME",
        f"{normalized_prefix}DB_USER",
        f"{normalized_prefix}USERNAME",
    )
    password = _get_env_value(
        f"{normalized_prefix}DATABASE_PASSWORD",
        f"{normalized_prefix}DB_PASSWORD",
        f"{normalized_prefix}PASSWORD",
    )

    return _normalize_mysql_url(url, username, password)


class DatabaseSettings(BaseModel):
    source_url: str = Field(..., description="SQLAlchemy URL for the source database")
    target_url: str = Field(..., description="SQLAlchemy URL for the target database")


class SchedulerSettings(BaseModel):
    cron_expression: str = Field(default="0 1 * * *", description="Cron for the daily ETL job")
    faq_cron_expression: str = Field(default="0 3 * * *", description="Cron for the daily FAQ extraction job")
    timezone: str = Field(default="Asia/Shanghai")
    max_workers: int = Field(default=4, ge=1, le=64)
    faq_max_workers: int = Field(default=5, ge=1, le=32)


class AicoSettings(BaseModel):
    host: str = Field(default=_get_env_value("AICO_HOST", default="20.17.39.132"))
    user_port: int = Field(default=int(_get_env_value("AICO_USER_PORT", default="11105")))
    project_port: int = Field(default=int(_get_env_value("AICO_PROJECT_PORT", default="39810")))
    kb_port: int = Field(default=int(_get_env_value("AICO_KB_PORT", default="11105")))
    timeout_seconds: float = Field(default=float(_get_env_value("AICO_TIMEOUT", default="10")))
    chatbot_url: str = Field(
        default=_get_env_value(
            "AICO_CHATBOT_URL",
            default="http://20.17.39.169:11105/aicoapi/gateway/v2/chatbot/api_run/1765187112_d4db36b1-5ef3-48f7-85b7-b35e9da02f96",
        )
    )
    chatbot_api_key: str = Field(default=_get_env_value("AICO_CHATBOT_API_KEY", default=""))


class AuthSettings(BaseModel):
    secret_key: str = Field(
        default=_get_env_value("AUTH_SECRET_KEY", default="change-this-secret"),
        description="Secret key for signing JWT tokens",
    )
    algorithm: str = Field(
        default=_get_env_value("AUTH_ALGORITHM", default="HS256"),
        description="JWT signing algorithm",
    )
    access_token_expires_minutes: int = Field(
        default=int(_get_env_value("AUTH_ACCESS_TOKEN_EXPIRES_MINUTES", default="10080")),
        description="Access token expiry in minutes",
    )


class Settings(BaseModel):
    app_name: str = "dialog-etl-service"
    environment: str = Field(default=_get_env_value("APP_ENV", default="prod"))
    log_level: str = Field(default=_get_env_value("LOG_LEVEL", default="INFO"))
    database: DatabaseSettings
    scheduler: SchedulerSettings
    aico: AicoSettings = AicoSettings()
    auth: AuthSettings = AuthSettings()


@lru_cache
def get_settings() -> Settings:
    default_url = _resolve_database_url()
    scheduler = SchedulerSettings(
        cron_expression=_get_env_value("ETL_CRON", default="0 1 * * *"),
        faq_cron_expression=_get_env_value("FAQ_CRON", default="0 3 * * *"),
        timezone=_get_env_value("APP_TIMEZONE", default="Asia/Shanghai"),
        max_workers=int(_get_env_value("ETL_MAX_WORKERS", default="4")),
        faq_max_workers=int(_get_env_value("FAQ_MAX_WORKERS", default="5")),
    )
    database = DatabaseSettings(
        source_url=_resolve_database_url("SRC_", fallback=default_url),
        target_url=_resolve_database_url("DST_", fallback=default_url),
    )
    return Settings(database=database, scheduler=scheduler)
