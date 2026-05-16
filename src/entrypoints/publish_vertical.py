"""Generate and publish daily vertical videos."""

import asyncio
import datetime
from dataclasses import dataclass
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
from src.infrastructure.storage.operational_metrics_repository import OperationalMetricsRepository
from src.infrastructure.storage.publisher_state_repository import PublisherStateRepository
from src.infrastructure.storage.release_repository import ReleaseRepository
from src.infrastructure.storage.timeseries_repository import TimeSeriesRepository
from src.infrastructure.storage.video_repository import VideoRepository
from src.shared.execution_lock import FileExecutionLock
from src.shared.logging import get_logger, setup_logging

logger = get_logger(__name__)


@dataclass(frozen=True)
class VerticalPublishJobContext:
    """Dependencies and configuration for vertical publish job."""

    timeseries_repo: TimeSeriesRepository
    video_repo: VideoRepository
    release_repo: ReleaseRepository
    publishers: list
    publish_vertical_use_case: PublishVerticalUseCase
    spotify_playlist_updater: SpotifyPlaylistUpdaterAdapter
    vertical_video_pipeline: VerticalVideoPipelineAdapter
    video_publish_executor: VideoPublishExecutorAdapter
    fetch_videos_use_case: FetchTopVideosUseCase


def _build_repositories(settings: AppSettings) -> tuple[TimeSeriesRepository, VideoRepository, ReleaseRepository]:
    """Factory: build all storage repositories with correct file paths."""
    db_video_file = settings.db_video_file
    db_release_file = settings.db_release_file
    db_timeseries_file = settings.db_timeseries_file

    if not settings.is_production_env:
        db_video_file += ".test"
        db_release_file += ".test"
        db_timeseries_file += ".test"

    return (
        TimeSeriesRepository(db_timeseries_file),
        VideoRepository(Path(db_video_file)),
        ReleaseRepository(db_release_file),
    )


def _build_job_dependencies(
    timeseries_repo: TimeSeriesRepository,
    video_repo: VideoRepository,
    release_repo: ReleaseRepository,
    settings: AppSettings,
) -> VerticalPublishJobContext:
    """Factory: build all adapters, use cases, and orchestration dependencies."""
    db_publishers_file = settings.db_release_file.replace("db_release", "db_publishers")
    if not settings.is_production_env:
        db_publishers_file += ".test"
    state_reader = PublisherStateRepository(db_publishers_file)
    publishers = build_publishers(state_reader)
    publish_vertical_use_case = PublishVerticalUseCase()
    spotify_playlist_updater = SpotifyPlaylistUpdaterAdapter(SpotifyClient())
    vertical_video_pipeline = VerticalVideoPipelineAdapter(settings)
    video_publish_executor = VideoPublishExecutorAdapter()
    fetch_videos_use_case = FetchTopVideosUseCase(timeseries_repo, video_repo)

    return VerticalPublishJobContext(
        timeseries_repo=timeseries_repo,
        video_repo=video_repo,
        release_repo=release_repo,
        publishers=publishers,
        publish_vertical_use_case=publish_vertical_use_case,
        spotify_playlist_updater=spotify_playlist_updater,
        vertical_video_pipeline=vertical_video_pipeline,
        video_publish_executor=video_publish_executor,
        fetch_videos_use_case=fetch_videos_use_case,
    )


async def main_async() -> None:
    settings = get_app_settings()
    with FileExecutionLock(Path(settings.scheduler_lock_file), "vertical_publish") as execution_lock:
        if not execution_lock.acquired:
            return
        await _run_vertical_publish_job(settings)


async def _run_vertical_publish_job(settings: AppSettings) -> None:
    metrics_db_path = (
        settings.db_timeseries_file if settings.is_production_env else f"{settings.db_timeseries_file}.test"
    )
    metrics_repo = OperationalMetricsRepository(
        metrics_db_path,
        retention_days=settings.operational_metrics_retention_days,
    )

    try:
        day = datetime.datetime.now(UTC).date()

        # Build dependencies
        timeseries_repo, video_repo, release_repo = _build_repositories(settings)
        job = _build_job_dependencies(timeseries_repo, video_repo, release_repo, settings)

        # Build job context
        job_context = await job.publish_vertical_use_case.build_job_context(
            release_store=job.release_repo,
            publishers=job.publishers,
            fetch_top_videos_use_case=job.fetch_videos_use_case,
            day=day,
            spotify_playlist_original=settings.spotify_playlist_original,
            is_spotify_configured=settings.is_spotify_configured,
        )

        if not job_context.has_any_work:
            logger.info("publish_vertical.already_completed", day=str(day))
            metrics_repo.record_metric_event(stage="processing", is_error=False)
            return

        # Publish Spotify playlist if needed
        await job.publish_vertical_use_case.maybe_update_spotify_original_playlist(
            release_store=job.release_repo,
            spotify_playlist_updater=job.spotify_playlist_updater,
            spotify_release_pending=job_context.spotify_release_pending,
            spotify_playlist_original=settings.spotify_playlist_original,
            spotify_user_id=settings.spotify_user_id,
            video_list=job_context.video_list,
        )

        if not job_context.pending_publishers:
            logger.info("publish_vertical.no_pending_publishers", day=str(day))
            metrics_repo.record_metric_event(stage="processing", is_error=False)
            return

        # Publish pending vertical videos
        await job.publish_vertical_use_case.publish_pending_vertical_videos(
            release_store=job.release_repo,
            publish_executor=job.video_publish_executor,
            vertical_video_pipeline=job.vertical_video_pipeline,
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
        metrics_repo.record_metric_event(stage="processing", is_error=False)
    except Exception:
        metrics_repo.record_metric_event(stage="processing", is_error=True)
        raise
    finally:
        metrics_repo.close()


def main() -> None:
    """Entry point for publish-vertical command."""
    settings = get_app_settings()
    setup_logging(settings.log_file_path)
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
