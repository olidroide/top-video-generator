"""Use case for loading the top-videos dashboard page."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from src.application.fetch_top_videos_use_case import FetchTopVideosRequest, FetchTopVideosUseCase
from src.domain.exceptions import ScoringError
from src.domain.models import ReleasePlatform, TimeseriesRange, Video
from src.shared.logging import get_logger

if TYPE_CHECKING:
    from src.domain.ports import ReleaseDateValidator

logger = get_logger(__name__)


@dataclass(frozen=True)
class GetTopVideosDashboardRequest:
    """Request data for the dashboard use case."""

    timeseries_range: TimeseriesRange
    day: date | None = None
    limit: int = 25


@dataclass(frozen=True)
class GetTopVideosDashboardResult:
    """Result payload consumed by the SSR dashboard view."""

    videos: tuple[Video, ...]
    yt_video_published: bool
    error_message: str | None = None


class GetTopVideosDashboardUseCase:
    """Compose the top-videos fetcher with the release status lookup."""

    def __init__(self, fetch_videos: FetchTopVideosUseCase, release_port: ReleaseDateValidator) -> None:
        self._fetch_videos = fetch_videos
        self._release_port = release_port

    async def execute(self, request: GetTopVideosDashboardRequest) -> GetTopVideosDashboardResult:
        day = request.day or datetime.now(UTC).date()

        try:
            videos_result = await self._fetch_videos.execute(
                FetchTopVideosRequest(
                    timeseries_range=request.timeseries_range,
                    day=day,
                    limit=request.limit,
                )
            )
        except ScoringError as exc:
            logger.warning("dashboard.fetch_failed", error=str(exc))
            return GetTopVideosDashboardResult(videos=(), yt_video_published=False, error_message=str(exc))

        yt_video_published = self._release_port.is_release_at_date(
            platform=ReleasePlatform.YOUTUBE.value,
            release_date=day,
        )

        return GetTopVideosDashboardResult(
            videos=videos_result.videos,
            yt_video_published=yt_video_published,
        )
