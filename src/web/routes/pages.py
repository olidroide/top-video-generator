"""SSR page routes."""

from datetime import UTC, date, datetime

import flag
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from starlette.responses import Response

from src.application.get_top_videos_dashboard_use_case import GetTopVideosDashboardRequest
from src.domain.models import TimeseriesRange
from src.web.dependencies import AppSettingsDep, GetTopVideosDashboardUseCaseDep
from src.web.state import logger, request_had_any_credentials, templates
from src.web.viewmodels import build_index_page_view_model

router = APIRouter()

_ISO_ALPHA2_LENGTH = 2
_MIN_DAILY_DATE = date(2020, 1, 1)


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
    use_case: GetTopVideosDashboardUseCaseDep,
    settings: AppSettingsDep,
    daily: date | None = None,
    weekly: date | None = None,
) -> Response:
    timeseries_range = TimeseriesRange.WEEKLY if weekly else TimeseriesRange.DAILY
    today = datetime.now(UTC).date()

    if daily is not None and daily < _MIN_DAILY_DATE:
        raise HTTPException(status_code=400, detail="Daily date out of range")

    current_date = weekly or daily or today

    logger.debug(
        "index_page_requested",
        requested_daily=str(daily) if daily else None,
        requested_weekly=str(weekly) if weekly else None,
        resolved_date=str(current_date),
        timeseries_range=timeseries_range.value,
    )

    result = await use_case.execute(
        GetTopVideosDashboardRequest(
            timeseries_range=timeseries_range,
            day=current_date,
            limit=25,
        )
    )
    credentials_owner = await request_had_any_credentials(request)
    title_flag = _title_flag(settings.yt_search_region_code)
    view_model = build_index_page_view_model(
        title_flag=title_flag,
        videos=result.videos,
        today=today,
        current_date=current_date,
        min_daily_date=_MIN_DAILY_DATE,
        is_weekly=weekly is not None,
        yt_video_published=result.yt_video_published,
        credentials_owner=credentials_owner,
        error_message=result.error_message,
    )

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"request": request, "vm": view_model},
    )
