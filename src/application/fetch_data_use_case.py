"""Fetch data orchestration use case."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from src.domain.models import Channel, VideoPoint
from src.domain.services.scoring_service import score_and_rank_video_points
from src.infrastructure.storage.timeseries_repository import TimeSeriesRepository
from src.infrastructure.storage.video_repository import VideoRepository
from src.shared.logging import get_logger

if TYPE_CHECKING:
    from src.adapters.youtube_source import YouTubeSource
    from src.config.settings import AppSettings

logger = get_logger(__name__)


class FetchDataUseCase:
    """Orchestrates fetching trending videos and storing timeseries data."""

    def __init__(
        self,
        youtube_source: YouTubeSource,
        video_repo: VideoRepository,
        timeseries_repo: TimeSeriesRepository,
        settings: AppSettings | None = None,
    ) -> None:
        self.youtube_source = youtube_source
        self.video_repo = video_repo
        self.timeseries_repo = timeseries_repo
        self.settings = settings

    async def execute(self) -> list[VideoPoint]:
        """Execute the fetch data workflow.

        Returns:
            List of VideoPoint objects that were added to timeseries.
        """
        settings = self.settings or self._get_settings()
        db_data_file = settings.db_data_file
        db_timeseries_file = settings.db_timeseries_file

        # Repositories are already injected, but we need to ensure they use correct paths
        # This maintains backward compatibility with existing repository constructors
        video_repo = VideoRepository(Path(db_data_file))
        timeseries_repo = TimeSeriesRepository(db_timeseries_file)

        if not await self._is_passed_enough_time_from_last_fetch(timeseries_repo):
            logger.debug("Not enough time elapsed since last fetch")
            return []

        last_timestamp = timeseries_repo.get_last_timestamp()
        if last_timestamp:
            from_dt = last_timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
            until_dt = from_dt + timedelta(days=1)
            last_timeseries_videos_fetched = timeseries_repo.get_video_points_by_date_range(from_dt, until_dt)
        else:
            last_timeseries_videos_fetched = []

        current_timeseries_videos_fetched: list[VideoPoint] = []

        trending_videos = await self.youtube_source.fetch_trending_videos(
            region=settings.yt_search_region_code,
            limit=25,
        )
        video_id_list = [v.video_id for v in trending_videos]

        # Step 2: fetch full video details in batch
        details = await self.youtube_source.fetch_video_details_batch(video_id_list)

        for video_item in details:
            logger.debug("video details", video_details=video_item.model_dump())
            video_repo.upsert(video_item)

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
        for video_point in scored_points:
            timeseries_repo.add_video_point(video_point=video_point)

        logger.info(
            "Finish fetch YT Data",
            count=len(current_timeseries_videos_fetched),
        )
        return current_timeseries_videos_fetched

    def _get_settings(self) -> AppSettings:
        """Get application settings."""
        from src.config.settings import get_app_settings

        return get_app_settings()

    async def _is_passed_enough_time_from_last_fetch(
        self, timeseries_repo: TimeSeriesRepository, min_days: int = 1
    ) -> bool:
        """Check if enough time has passed since last fetch."""
        if not (last_timeseries_datetime := timeseries_repo.get_last_timestamp()):
            logger.debug("No timeseries found")
            return True
        last_timeseries_datetime = last_timeseries_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
        current_datetime = datetime.now(UTC)
        delta_from_last_recollection = current_datetime - last_timeseries_datetime

        if not (is_enough_time := delta_from_last_recollection.days >= min_days):
            logger.debug(
                "fetch_data.not_enough_time_elapsed",
                min_days=min_days,
                delta=str(delta_from_last_recollection),
            )
        return is_enough_time
