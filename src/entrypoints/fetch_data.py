"""Fetch trending YouTube videos and store timeseries data."""

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

from src.adapters.youtube_source import YouTubeSource
from src.application.fetch_trending_use_case import FetchTrendingRequest, FetchTrendingUseCase
from src.config.settings import AppSettings, get_app_settings
from src.domain.models import Channel, VideoPoint
from src.domain.services.scoring_service import score_and_rank_video_points
from src.infrastructure.storage.timeseries_repository import TimeSeriesRepository
from src.infrastructure.storage.video_repository import VideoRepository
from src.shared.execution_lock import FileExecutionLock
from src.shared.logging import get_logger, setup_logging

logger = get_logger(__name__)


async def is_passed_enough_time_from_last_fetch(
    timeseries_repo: TimeSeriesRepository,
    min_days: int = 1,
) -> bool:
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


async def main_async() -> None:
    settings = get_app_settings()
    with FileExecutionLock(Path(settings.scheduler_lock_file), "fetch_data") as execution_lock:
        if not execution_lock.acquired:
            return
        await _run_fetch_data_job(settings)


async def _run_fetch_data_job(settings: AppSettings | None = None) -> None:
    start_process_datetime = datetime.now(UTC)
    settings = settings if settings is not None else get_app_settings()
    db_data_file = settings.db_data_file
    db_timeseries_file = settings.db_timeseries_file

    timeseries_repo = TimeSeriesRepository(db_timeseries_file)
    video_repo = VideoRepository(Path(db_data_file))

    if not await is_passed_enough_time_from_last_fetch(timeseries_repo=timeseries_repo):
        return

    last_timestamp = timeseries_repo.get_last_timestamp()
    if last_timestamp:
        from_dt = last_timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        until_dt = from_dt + timedelta(days=1)
        last_timeseries_videos_fetched = timeseries_repo.get_video_points_by_date_range(from_dt, until_dt)
    else:
        last_timeseries_videos_fetched = []

    current_timeseries_videos_fetched: list[VideoPoint] = []

    yt_source = YouTubeSource()
    fetch_trending_use_case = FetchTrendingUseCase(source=yt_source)
    trending_result = await fetch_trending_use_case.execute(
        FetchTrendingRequest(region=settings.yt_search_region_code, limit=25)
    )
    video_id_list = [v.video_id for v in trending_result.videos]

    # Paso 2: obtener detalles completos en batch
    details = await yt_source.fetch_video_details_batch(video_id_list)

    for video_item in details:
        logger.debug("video details", video_details=video_item.model_dump())
        video_repo.upsert(video_item)

        last_video_point = VideoPoint(
            time=start_process_datetime,
            video_id=video_item.video_id,
            views=video_item.views,
            likes=video_item.likes,
            title=video_item.title or None,
            description=video_item.description or None,
            channel=Channel(name=video_item.channel_name) if video_item.channel_name else None,
            duration=int(video_item.duration_seconds) if video_item.duration_seconds > 0 else None,
        )
        current_timeseries_videos_fetched.append(last_video_point)

    for video_point in score_and_rank_video_points(current_timeseries_videos_fetched, last_timeseries_videos_fetched):
        timeseries_repo.add_video_point(video_point=video_point)

    logger.info("Finish fetch YT Data", current_timeseries_videos_fetched=current_timeseries_videos_fetched)


def main() -> None:
    """Entry point for fetch-data command."""
    settings = get_app_settings()
    setup_logging(settings.log_file_path)
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
