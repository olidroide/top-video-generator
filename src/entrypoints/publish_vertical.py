"""Generate and publish daily vertical videos."""

import asyncio
import datetime
from datetime import UTC
from pathlib import Path

from src.adapters.spotify_playlist_updater import SpotifyPlaylistUpdaterAdapter
from src.adapters.vertical_video_pipeline import VerticalVideoPipelineAdapter
from src.adapters.video_publish_executor import VideoPublishExecutorAdapter
from src.application.fetch_top_videos_use_case import FetchTopVideosUseCase
from src.application.publish_vertical_use_case import (
    PublisherClientIdentity,
    PublishVerticalUseCase,
)
from src.config.settings import AppSettings, get_app_settings
from src.infrastructure.publisher_registry import build_publishers
from src.infrastructure.social.spotify_client import SpotifyClient
from src.infrastructure.storage.release_repository import ReleaseRepository
from src.infrastructure.storage.timeseries_repository import TimeSeriesRepository
from src.infrastructure.storage.video_repository import VideoRepository
from src.shared.execution_lock import FileExecutionLock
from src.shared.logging import get_logger, setup_logging

logger = get_logger(__name__)


async def main_async() -> None:
    settings = get_app_settings()
    with FileExecutionLock(Path(settings.scheduler_lock_file), "vertical_publish") as execution_lock:
        if not execution_lock.acquired:
            return
        await _run_vertical_publish_job(settings)


async def _run_vertical_publish_job(settings: AppSettings) -> None:
    day = datetime.datetime.now(UTC).date()
    db_video_file = settings.db_video_file
    db_release_file = settings.db_release_file
    db_timeseries_file = settings.db_timeseries_file

    # Initialize repositories
    timeseries_repo = TimeSeriesRepository(db_timeseries_file)
    video_repo = VideoRepository(Path(db_video_file))
    release_repo = ReleaseRepository(db_release_file)
    publishers = build_publishers()
    publish_vertical_use_case = PublishVerticalUseCase()
    spotify_playlist_updater = SpotifyPlaylistUpdaterAdapter(SpotifyClient())
    vertical_video_pipeline = VerticalVideoPipelineAdapter(settings)
    video_publish_executor = VideoPublishExecutorAdapter()

    fetch_videos_use_case = FetchTopVideosUseCase(timeseries_repo, video_repo)
    job_context = await publish_vertical_use_case.build_job_context(
        release_store=release_repo,
        publishers=publishers,
        fetch_top_videos_use_case=fetch_videos_use_case,
        day=day,
        spotify_playlist_original=settings.spotify_playlist_original,
        is_spotify_configured=settings.is_spotify_configured,
    )

    if not job_context.has_any_work:
        logger.info("publish_vertical.already_completed", day=str(day))
        return

    await publish_vertical_use_case.maybe_update_spotify_original_playlist(
        release_store=release_repo,
        spotify_playlist_updater=spotify_playlist_updater,
        spotify_release_pending=job_context.spotify_release_pending,
        spotify_playlist_original=settings.spotify_playlist_original,
        spotify_user_id=settings.spotify_user_id,
        video_list=job_context.video_list,
    )

    if not job_context.pending_publishers:
        logger.info("publish_vertical.no_pending_publishers", day=str(day))
        return

    await publish_vertical_use_case.publish_pending_vertical_videos(
        release_store=release_repo,
        publish_executor=video_publish_executor,
        vertical_video_pipeline=vertical_video_pipeline,
        pending_publishers=job_context.pending_publishers,
        video_list=job_context.video_list,
        publisher_client_identity=PublisherClientIdentity(
            youtube_client_id=settings.yt_auth_user_id,
            instagram_client_id=settings.instagram_client_username,
            tiktok_client_id=settings.tiktok_user_openid,
        ),
        yt_title_template=settings.yt_title_template,
        yt_description_template=settings.yt_description_template,
    )


def main() -> None:
    """Entry point for publish-vertical command."""
    settings = get_app_settings()
    setup_logging(settings.log_file_path)
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
