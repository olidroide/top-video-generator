"""Use case for fetching and ranking top videos by growth."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from src.domain.models import Channel, TimeseriesRange, Video, VideoPoint
from src.domain.services.scoring_service import datetime_range_start, score_and_rank_video_points
from src.shared.logging import get_logger

if TYPE_CHECKING:
    from pydantic import PastDate

    from src.domain.ports import TimeSeriesPort, VideoMetadataPort

logger = get_logger(__name__)


@dataclass(frozen=True)
class FetchTopVideosRequest:
    """Request to fetch top-ranked videos for a period."""

    timeseries_range: TimeseriesRange = TimeseriesRange.WEEKLY
    day: PastDate | None = None
    limit: int = 25


@dataclass(frozen=True)
class FetchTopVideosResult:
    """Result containing ranked video list."""

    videos: tuple[Video, ...]

    @property
    def video_count(self) -> int:
        """Number of videos in result."""
        return len(self.videos)


class FetchTopVideosUseCase:
    """
    Fetch and rank videos by growth over a time range.

    Algorithm:
    1. Fetch previous period's videos (baseline for comparison)
    2. Fetch current period's videos
    3. Calculate growth, assign ranking and status (NEW/UP/DOWN/EQUAL)
    4. Return ranked list
    """

    def __init__(
        self,
        timeseries_repo: TimeSeriesPort,
        video_metadata_repo: VideoMetadataPort,
    ) -> None:
        """Initialize with repository."""
        self._timeseries_repo = timeseries_repo
        self._video_metadata_repo = video_metadata_repo

    async def execute(self, request: FetchTopVideosRequest) -> FetchTopVideosResult:
        """Execute ranking workflow."""
        day = request.day or datetime.now(UTC).date()

        # Fetch previous period
        previous_list = self._get_defined_range_timeseries_videos(request.timeseries_range, day)

        # Fetch current period (today)
        current_list = self._get_defined_range_timeseries_videos(TimeseriesRange.DAILY, day + timedelta(days=1))

        if not current_list:
            error_msg = "No video timeseries for today; run fetch script first"
            logger.error(error_msg)
            raise IndexError(error_msg)

        # Rank and compare
        ranked = score_and_rank_video_points(current_list, previous_list)

        # Hydrate ranked points with canonical metadata from the video repository.
        hydrated_ranked = [self._hydrate_video_metadata(video_point) for video_point in ranked[: request.limit]]
        videos = tuple(Video.model_validate(video_point.model_dump()) for video_point in hydrated_ranked)

        return FetchTopVideosResult(videos=videos)

    def _hydrate_video_metadata(self, video_point: VideoPoint) -> VideoPoint:
        """Enrich a timeseries point with canonical metadata when available."""
        canonical_video = self._video_metadata_repo.get(video_point.video_id)
        if canonical_video is None:
            return video_point

        channel_name = canonical_video.channel_name or (
            video_point.channel.name if video_point.channel and video_point.channel.name else None
        )
        duration = (
            int(canonical_video.duration_seconds) if canonical_video.duration_seconds > 0 else video_point.duration
        )

        return video_point.model_copy(
            update={
                "title": canonical_video.title or video_point.title,
                "description": canonical_video.description or video_point.description,
                "channel": Channel(name=channel_name) if channel_name else video_point.channel,
                "duration": duration,
            }
        )

    def _get_defined_range_timeseries_videos(
        self,
        timeseries_range: TimeseriesRange,
        day: PastDate,
    ) -> list[VideoPoint]:
        """Fetch VideoPoints from a specific date range."""
        from_dt = self._calculate_datetime_for_range(timeseries_range, day)
        until_dt = from_dt + timedelta(days=1)
        return self._timeseries_repo.get_video_points_by_date_range(from_dt, until_dt)

    @staticmethod
    def _calculate_datetime_for_range(
        timeseries_range: TimeseriesRange,
        day: PastDate,
    ) -> datetime:
        """Calculate start datetime for a time range."""
        map_range_days = {TimeseriesRange.DAILY: 1, TimeseriesRange.WEEKLY: 7}
        from_days_ago = map_range_days.get(timeseries_range, 7)
        return datetime_range_start(from_days_ago, reference=day)
