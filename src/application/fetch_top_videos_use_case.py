"""Use case for fetching and ranking top videos by growth."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from pydantic import PastDate

from src.domain.models import TimeseriesRange, Video, VideoPoint, VideoScoreStatus
from src.domain.ports import TimeSeriesPort
from src.shared.logging import get_logger

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
    ) -> None:
        """Initialize with repository."""
        self._timeseries_repo = timeseries_repo

    async def execute(self, request: FetchTopVideosRequest) -> FetchTopVideosResult:
        """Execute ranking workflow."""
        day = request.day or date.today()

        # Fetch previous period
        previous_list = self._get_defined_range_timeseries_videos(request.timeseries_range, day)

        # Fetch current period (today)
        current_list = self._get_defined_range_timeseries_videos(TimeseriesRange.DAILY, day + timedelta(days=1))

        if not current_list:
            error_msg = "No video timeseries for today; run fetch script first"
            logger.error(error_msg)
            raise IndexError(error_msg)

        # Rank and compare
        ranked = self._generate_top_list_compared(current_list, previous_list)

        # Convert to Video models and limit
        videos = tuple(Video.model_validate(vp.model_dump()) for vp in ranked[: request.limit])

        return FetchTopVideosResult(videos=videos)

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
        from_datetime = datetime.combine(day, datetime.min.time(), tzinfo=UTC)
        return from_datetime - timedelta(days=from_days_ago)

    @staticmethod
    def _generate_top_list_compared(
        current_video_list: list[VideoPoint],
        previous_video_list: list[VideoPoint],
    ) -> list[VideoPoint]:
        """Rank current videos by growth, compare with previous state."""
        previous_map = {v.video_id: v for v in previous_video_list}

        # Calculate growth
        for video_point in current_video_list:
            prev = previous_map.get(video_point.video_id)
            if prev:
                video_point.views_growth = abs(video_point.views - prev.views)
            else:
                video_point.views_growth = video_point.views_growth or video_point.views

        # Sort by growth DESC
        current_video_list.sort(key=lambda x: x.views_growth or 0, reverse=True)

        # Assign ranks and status
        for rank, video_point in enumerate(current_video_list, start=1):
            prev = previous_map.get(video_point.video_id)
            prev_score = float(prev.score) if prev and prev.score else None
            video_point.score = rank
            video_point.score_previous = prev_score

            # Status: compare rank with previous rank (lower rank score = higher ranking)
            if not prev_score:
                video_point.score_status = VideoScoreStatus.NEW
            elif video_point.score == prev_score:
                video_point.score_status = VideoScoreStatus.EQUAL
            elif video_point.score > prev_score:
                video_point.score_status = VideoScoreStatus.DOWN
            else:
                video_point.score_status = VideoScoreStatus.UP

        return current_video_list
