"""Fetch trending YouTube videos and store timeseries data."""

import asyncio
from pathlib import Path

from src.adapters.youtube_source import YouTubeSource
from src.application.fetch_data_use_case import FetchDataUseCase
from src.config.settings import PROJECT_ROOT, AppSettings, get_app_settings
from src.infrastructure.storage.timeseries_repository import TimeSeriesRepository
from src.infrastructure.storage.video_repository import VideoRepository
from src.shared.execution_lock import FileExecutionLock
from src.shared.logging import get_logger, setup_logging

logger = get_logger(__name__)


def _resolve_project_path(path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else PROJECT_ROOT / path


async def main_async() -> None:
    settings = get_app_settings()
    with FileExecutionLock(Path(settings.scheduler_lock_file), "fetch_data") as execution_lock:
        if not execution_lock.acquired:
            return
        await _run_fetch_data_job(settings)


async def _run_fetch_data_job(settings: AppSettings | None = None) -> None:
    settings = settings if settings is not None else get_app_settings()
    db_video_file = _resolve_project_path(settings.db_video_file)
    db_timeseries_file = _resolve_project_path(settings.db_timeseries_file)

    youtube_source = YouTubeSource(settings=settings)
    video_repo = VideoRepository(db_video_file)
    timeseries_repo = TimeSeriesRepository(str(db_timeseries_file))

    fetch_data_use_case = FetchDataUseCase(
        youtube_source=youtube_source,
        video_repo=video_repo,
        timeseries_repo=timeseries_repo,
        settings=settings,
    )

    await fetch_data_use_case.execute()


def main() -> None:
    """Entry point for fetch-data command."""
    settings = get_app_settings()
    setup_logging(settings.log_file_path)
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
