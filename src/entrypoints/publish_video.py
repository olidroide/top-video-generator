"""Generate and publish weekly horizontal videos."""

import asyncio
import datetime
from datetime import UTC
from pathlib import Path

from src.adapters.horizontal_video_pipeline import HorizontalVideoPipelineAdapter
from src.adapters.youtube_weekly_uploader import YouTubeWeeklyUploaderAdapter
from src.application.fetch_top_videos_use_case import FetchTopVideosUseCase
from src.application.publish_video_use_case import WeeklyHorizontalPublishRequest, WeeklyHorizontalPublishUseCase
from src.config.settings import AppSettings, get_app_settings
from src.infrastructure.storage.operational_metrics_repository import OperationalMetricsRepository
from src.infrastructure.storage.release_repository import ReleaseRepository
from src.infrastructure.storage.timeseries_repository import TimeSeriesRepository
from src.infrastructure.storage.video_repository import VideoRepository
from src.shared.execution_lock import FileExecutionLock
from src.shared.logging import get_logger, setup_logging

logger = get_logger(__name__)


def _resolve_storage_paths(settings: AppSettings) -> tuple[str, str, str, str]:
    db_video_file = settings.db_video_file
    db_release_file = settings.db_release_file
    db_timeseries_file = settings.db_timeseries_file
    metrics_db_path = settings.db_timeseries_file

    if not settings.is_production_env:
        db_video_file += ".test"
        db_release_file += ".test"
        db_timeseries_file += ".test"
        metrics_db_path += ".test"

    return db_video_file, db_release_file, db_timeseries_file, metrics_db_path


async def main_async() -> None:
    settings = get_app_settings()
    with FileExecutionLock(Path(settings.scheduler_lock_file), "weekly_publish") as execution_lock:
        if not execution_lock.acquired:
            return
        await _run_weekly_publish_job(settings)


async def _run_weekly_publish_job(settings: AppSettings) -> None:
    db_video_file, db_release_file, db_timeseries_file, metrics_db_path = _resolve_storage_paths(settings)
    metrics_repo = OperationalMetricsRepository(
        metrics_db_path,
        retention_days=settings.operational_metrics_retention_days,
    )

    try:
        day = datetime.datetime.now(UTC).date()
        release_repo = ReleaseRepository(db_release_file)
        fetch_videos_use_case = FetchTopVideosUseCase(
            TimeSeriesRepository(db_timeseries_file),
            VideoRepository(Path(db_video_file)),
        )
        use_case = WeeklyHorizontalPublishUseCase(
            release_store=release_repo,
            fetch_top_videos_use_case=fetch_videos_use_case,
            horizontal_video_pipeline=HorizontalVideoPipelineAdapter(settings),
            uploader=YouTubeWeeklyUploaderAdapter(),
        )

        result = await use_case.execute(
            WeeklyHorizontalPublishRequest(
                day=day,
                yt_title_template=settings.yt_title_template,
                yt_description_template=settings.yt_description_template,
                yt_playlist_id_weekly=settings.yt_playlist_id_weekly,
                yt_auth_user_id=settings.yt_auth_user_id,
            )
        )
        metrics_repo.record_metric_event(stage="upload", is_error=not result.success)
    except Exception:
        metrics_repo.record_metric_event(stage="upload", is_error=True)
        raise
    finally:
        metrics_repo.close()


def main() -> None:
    """Entry point for publish-video command."""
    settings = get_app_settings()
    setup_logging(settings.log_file_path)
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
