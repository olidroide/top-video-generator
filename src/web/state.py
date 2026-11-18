"""Shared web-layer state and helpers."""

from datetime import UTC, datetime
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from src.shared.logging import get_logger
from src.web.csrf import get_csrf_token

logger = get_logger(__name__)
WEB_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))
templates.env.globals["csrf_token"] = get_csrf_token

ADMIN_SESSION_KEY = "admin_authenticated"
ADMIN_SESSION_ID_KEY = "admin_session_id"
YT_OAUTH_STATE_KEY = "yt_oauth_state"


def is_admin_authenticated(request: Request) -> bool:
    if not request.session.get(ADMIN_SESSION_KEY):
        return False
    session_id = request.session.get(ADMIN_SESSION_ID_KEY)
    if not isinstance(session_id, str) or not session_id:
        return False
    revoked_session_ids = getattr(request.app.state, "revoked_admin_sessions", set())
    return session_id not in revoked_session_ids


def _timestamp_to_time_label(timestamp: float) -> str:
    dt = datetime.fromtimestamp(timestamp, tz=UTC)
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


templates.env.filters["timestamp_to_time_label"] = _timestamp_to_time_label


@lru_cache(maxsize=1)
def get_app_version() -> str:
    try:
        return version("top-video-generator")
    except PackageNotFoundError:
        return "0.0.0"


class HealthCheck(BaseModel):
    status: str
    version: str = Field(default_factory=get_app_version)
    checks: dict[str, dict[str, str]]


async def request_had_any_credentials(request: Request) -> bool:
    return bool(request.session.get("yt_credentials") or request.session.get("tiktok_credentials"))
