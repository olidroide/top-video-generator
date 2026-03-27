"""Fetch trending YouTube videos and store timeseries data."""

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

from src.adapters.youtube_source import YouTubeSource
from src.application.fetch_trending_use_case import FetchTrendingRequest, FetchTrendingUseCase
from src.config.settings import get_app_settings
from src.domain.models import VideoPoint, VideoScoreStatus
from src.infrastructure.storage.timeseries_repository import TimeSeriesRepository
from src.infrastructure.storage.video_repository import VideoRepository
from src.shared.logging import get_logger

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
        logger.debug(f"Less than a {min_days} days ({delta_from_last_recollection}) to recollect data")
    return is_enough_time


def _rank_video_points(
    current_video_list: list[VideoPoint],
    previous_video_list: list[VideoPoint],
) -> list[VideoPoint]:
    previous_map = {v.video_id: v for v in previous_video_list}

    for video_point in current_video_list:
        prev = previous_map.get(video_point.video_id)
        if prev:
            video_point.views_growth = abs(video_point.views - prev.views)
        else:
            video_point.views_growth = video_point.views_growth or video_point.views

    current_video_list.sort(key=lambda x: x.views_growth or 0, reverse=True)

    for rank, video_point in enumerate(current_video_list, start=1):
        prev = previous_map.get(video_point.video_id)
        prev_score = float(prev.score) if prev and prev.score else None
        video_point.score = rank
        video_point.score_previous = prev_score

        if prev_score is None:
            video_point.score_status = VideoScoreStatus.NEW
        elif video_point.score == prev_score:
            video_point.score_status = VideoScoreStatus.EQUAL
        elif video_point.score > prev_score:
            video_point.score_status = VideoScoreStatus.DOWN
        else:
            video_point.score_status = VideoScoreStatus.UP

    return current_video_list


async def main_async():
    start_process_datetime = datetime.now(UTC)
    settings = get_app_settings()
    db_data_file = settings.db_data_file
    db_timeseries_file = settings.db_timeseries_file

    if not settings.is_production_env:
        db_data_file += ".test"
        db_timeseries_file += ".test"

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
        FetchTrendingRequest(region=settings.yt_search_region_code or "ES", limit=25)
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
        )
        current_timeseries_videos_fetched.append(last_video_point)

    for video_point in _rank_video_points(
        current_video_list=current_timeseries_videos_fetched,
        previous_video_list=last_timeseries_videos_fetched,
    ):
        timeseries_repo.add_video_point(video_point=video_point)

    logger.info("Finish fetch YT Data", current_timeseries_videos_fetched=current_timeseries_videos_fetched)


def main():
    """Entry point for fetch-data command."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
