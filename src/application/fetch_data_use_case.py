"""Fetch data orchestration use case."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from src.domain.models import Channel, VideoPoint
from src.domain.services.scoring_service import score_and_rank_video_points
from src.shared.logging import get_logger

if TYPE_CHECKING:
    from src.config.settings import AppSettings
    from src.domain.ports import TimeSeriesStore, TrendingVideoFetcher, VideoMetadataStore

logger = get_logger(__name__)


class FetchDataUseCase:
    """Orchestrates fetching trending videos and storing timeseries data."""

    def __init__(
        self,
        trending_fetcher: TrendingVideoFetcher | None = None,
        video_repo: VideoMetadataStore | None = None,
        timeseries_repo: TimeSeriesStore | None = None,
        settings: AppSettings | None = None,
        force_fetch: bool = False,
        *,
        youtube_source: TrendingVideoFetcher | None = None,
    ) -> None:
        source = trending_fetcher or youtube_source
        if source is None:
            raise ValueError("A trending video fetcher is required")
        if video_repo is None:
            raise ValueError("A video metadata store is required")
        if timeseries_repo is None:
            raise ValueError("A timeseries store is required")

        self.trending_fetcher = source
        self.youtube_source = source
        self.video_repo = video_repo
        self.timeseries_repo = timeseries_repo
        self.settings = settings
        self.force_fetch = force_fetch

    async def execute(self) -> list[VideoPoint]:
        """Execute the fetch data workflow.

        Returns:
            List of VideoPoint objects that were added to timeseries.
        """
        settings = self.settings or self._get_settings()

        if not self.force_fetch and not self._is_passed_enough_time_from_last_fetch():
            logger.debug("Not enough time elapsed since last fetch")
            return []

        if self.force_fetch:
            logger.info("fetch_data.manual_force_enabled")

        last_timestamp = self.timeseries_repo.get_last_timestamp()
        if last_timestamp:
            from_dt = last_timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
            until_dt = from_dt + timedelta(days=1)
            last_timeseries_videos_fetched = self.timeseries_repo.get_video_points_by_date_range(from_dt, until_dt)
        else:
            last_timeseries_videos_fetched = []

        current_timeseries_videos_fetched: list[VideoPoint] = []

        trending_videos = await self.trending_fetcher.fetch_trending_videos(
            region=settings.yt_search_region_code,
            limit=25,
        )
        video_id_list = [v.video_id for v in trending_videos]

        # Step 2: fetch full video details in batch
        details = await self.trending_fetcher.fetch_video_details_batch(video_id_list)

        for video_item in details:
            logger.debug("video details", video_details=video_item.model_dump())
            self.video_repo.upsert(video_item)

            last_video_point = VideoPoint(
                time=datetime.now(UTC),
                video_id=video_item.video_id,
                views=video_item.views,
                likes=video_item.likes,
                title=video_item.title or None,
                description=video_item.description or None,
                channel=Channel(name=video_item.channel_name) if video_item.channel_name else None,
                duration=int(video_item.duration_seconds) if video_item.duration_seconds > 0 else None,
            )
            current_timeseries_videos_fetched.append(last_video_point)

        scored_points = score_and_rank_video_points(current_timeseries_videos_fetched, last_timeseries_videos_fetched)
        zero_score_count = sum(1 for point in scored_points if (point.score or 0) <= 0)
        zero_growth_count = sum(1 for point in scored_points if (point.views_growth or 0) <= 0)

        logger.info(
            "fetch_data.scoring_summary",
            total=len(scored_points),
            zero_score_count=zero_score_count,
            zero_growth_count=zero_growth_count,
        )

        for video_point in scored_points:
            self.timeseries_repo.add_video_point(video_point=video_point)

        logger.info(
            "Finish fetch YT Data",
            count=len(current_timeseries_videos_fetched),
        )
        return scored_points

    def _get_settings(self) -> AppSettings:
        """Get application settings."""
        from src.config.settings import get_app_settings

        return get_app_settings()

    def _is_passed_enough_time_from_last_fetch(
        self,
        timeseries_repo: TimeSeriesStore | None = None,
        min_days: int = 1,
    ) -> bool:
        """Check if enough calendar days have passed since last fetch.

        Uses calendar-day comparison instead of strict elapsed seconds to prevent
        the scheduler from blocking a fetch when the previous run happened a few
        seconds after the scheduled time (e.g. last fetch at 15:15, next run at
        15:00 the following day = 23h45m < 86400s but clearly a new day).
        """
        repository = timeseries_repo or self.timeseries_repo
        if not (last_timeseries_datetime := repository.get_last_timestamp()):
            logger.debug("No timeseries found")
            return True
        current_date = datetime.now(UTC).date()
        last_date = last_timeseries_datetime.date()
        days_elapsed = (current_date - last_date).days

        if not (is_enough_time := days_elapsed >= min_days):
            logger.debug(
                "fetch_data.not_enough_time_elapsed",
                min_days=min_days,
                last_date=str(last_date),
                current_date=str(current_date),
                days_elapsed=days_elapsed,
            )
        return is_enough_time
