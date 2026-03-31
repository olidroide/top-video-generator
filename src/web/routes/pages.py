"""SSR page routes."""

from datetime import UTC, date, datetime, timedelta
from typing import Any

import flag
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, field_validator
from starlette.responses import Response

from src.application.fetch_top_videos_use_case import FetchTopVideosRequest
from src.domain.models import ReleasePlatform, TimeseriesRange
from src.web.dependencies import AppSettingsDep, FetchTopVideosUseCaseDep, ReleaseRepositoryDep
from src.web.state import logger, request_had_any_credentials, templates

router = APIRouter()

_ISO_ALPHA2_LENGTH = 2


class TimeseriesDailyDateModel(BaseModel):
    value: date

    @field_validator("value")
    @classmethod
    def validate_date(cls, v: date) -> date:
        return v


def _title_flag(region_code: str | None) -> str:
    candidate = (region_code or "").strip()
    if not candidate:
        return "🌍"
    if len(candidate) != _ISO_ALPHA2_LENGTH or not candidate.isalpha():
        logger.warning("invalid_title_region_code", region_code=candidate)
        return "🌍"

    try:
        return flag.flag(candidate)
    except flag.UnknownCountryCode:
        logger.warning("invalid_title_region_code", region_code=candidate)
        return "🌍"


@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    use_case: FetchTopVideosUseCaseDep,
    release_repo: ReleaseRepositoryDep,
    settings: AppSettingsDep,
    daily: TimeseriesDailyDateModel | None = None,
    weekly: TimeseriesDailyDateModel | None = None,
) -> Response:
    timeseries_range = TimeseriesRange.WEEKLY if weekly else TimeseriesRange.DAILY
    today = datetime.now(UTC).date()
    daily_date = today if not daily else daily.value
    weekly_date = weekly.value if weekly else None
    try:
        result = await use_case.execute(
            FetchTopVideosRequest(timeseries_range=timeseries_range, day=weekly_date or daily_date, limit=25)
        )
        video_list = list(result.videos)

        yt_video_published = release_repo.is_release_at_date(
            platform=ReleasePlatform.YOUTUBE.value,
            release_date=daily_date,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Error loading videos: {exc}")
        video_list = []
        yt_video_published = False

    credentials_owner = await request_had_any_credentials(request)
    title_flag = _title_flag(settings.yt_search_region_code)
    data_context: dict[str, Any] = {
        "request": request,
        "video_list": video_list,
        "timeseries_range": timeseries_range.value,
        "timeseries_weekly_date": weekly_date,
        "timeseries_daily_date": daily_date,
        "timeseries_next_date": daily_date + timedelta(days=1) if daily_date < today else None,
        "timeseries_previous_date": daily_date - timedelta(days=1),
        "yt_video_published": yt_video_published,
        "credentials_owner": credentials_owner,
        "title_page": f"{title_flag} 🔝 VIDEO GENERATOR",
    }

    return templates.TemplateResponse(request=request, name="index.html", context=data_context)
