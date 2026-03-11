"""Fetch trending YouTube videos and store timeseries data."""

import asyncio
from datetime import UTC, datetime

from src.adapters.youtube_source import YouTubeSource
from src.db_client import Channel, DatabaseClient, Video, VideoPoint, VideoPointTools
from src.domain.models import CanonicalVideo
from src.shared.logging import get_logger

logger = get_logger(__name__)


async def is_passed_enough_time_from_last_fetch(
    db_client: DatabaseClient,
    min_days: int = 1,
) -> bool:
    if not (last_timeseries_datetime := db_client.get_last_timeseries_datetime()):
        logger.debug("No timeseries found")
        return True
    last_timeseries_datetime = last_timeseries_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
    current_datetime = datetime.now(UTC)
    delta_from_last_recollection = current_datetime - last_timeseries_datetime

    if not (is_enough_time := delta_from_last_recollection.days >= min_days):
        logger.debug(f"Less than a {min_days} days ({delta_from_last_recollection}) to recollect data")
    return is_enough_time


async def main_async():
    start_process_datetime = datetime.now(UTC)
    db_client = DatabaseClient()
    if not await is_passed_enough_time_from_last_fetch(db_client=db_client):
        return

    yt_source = YouTubeSource()
    last_timeseries_videos_fetched: list[VideoPoint] = list(db_client.get_last_timeseries_videos())
    current_timeseries_videos_fetched: list[VideoPoint] = []

    # Paso 1: obtener videos trending (solo ids)
    trending: list[CanonicalVideo] = await yt_source.fetch_trending_videos(region="ES", limit=25)
    video_id_list = [v.video_id for v in trending]

    # Paso 2: obtener detalles completos en batch
    details: list[CanonicalVideo] = await yt_source.fetch_video_details_batch(video_id_list)

    def _canonical_to_db_video(v: CanonicalVideo) -> Video:
        """Mapea CanonicalVideo a Video para persistencia en TinyDB."""
        return Video(
            video_id=v.video_id,
            views=v.views,
            likes=v.likes,
            title=v.title,
            description=v.description,
            duration=int(v.duration_seconds) if v.duration_seconds is not None else None,
            channel=Channel(channel_id=None, name=v.channel_name),
        )

    for video_item in details:
        logger.debug("video details", video_details=video_item.model_dump())
        db_client.add_or_update_video(video=_canonical_to_db_video(video_item))

        last_video_point = VideoPoint(
            time=start_process_datetime,
            video_id=video_item.video_id,
            views=video_item.views,
            likes=video_item.likes,
        )
        current_timeseries_videos_fetched.append(last_video_point)

    for video_point in VideoPointTools.generate_top_list_compared(
        current_video_list=current_timeseries_videos_fetched,
        previous_video_list=last_timeseries_videos_fetched,
    ):
        db_client.add_video_point(video_point=video_point)

    logger.info("Finish fetch YT Data", current_timeseries_videos_fetched=current_timeseries_videos_fetched)


def main():
    """Entry point for fetch-data command."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
