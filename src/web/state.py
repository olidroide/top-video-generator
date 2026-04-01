"""Shared web-layer state and helpers."""

from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from src.shared.logging import get_logger

logger = get_logger(__name__)
WEB_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))

metrics_state = {
    "fetch_count": 0,
    "fetch_errors": 0,
    "upload_count": 0,
    "upload_errors": 0,
    "processing_count": 0,
    "processing_errors": 0,
}


class HealthCheck(BaseModel):
    status: str
    version: str = "1.0.0"
    checks: dict[str, dict[str, str]]


class MetricsResponse(BaseModel):
    fetch_count: int
    fetch_errors: int
    upload_count: int
    upload_errors: int
    processing_count: int
    processing_errors: int


async def request_had_any_credentials(request: Request) -> bool:
    return bool(
        request.session.get("yt_credentials")
        or request.session.get("tiktok_credentials")
        or request.session.get("spotify_credentials")
    )
