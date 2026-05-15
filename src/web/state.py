"""Shared web-layer state and helpers."""

from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from src.shared.logging import get_logger

logger = get_logger(__name__)
WEB_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))


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
    return bool(
        request.session.get("yt_credentials")
        or request.session.get("tiktok_credentials")
        or request.session.get("spotify_credentials")
    )
