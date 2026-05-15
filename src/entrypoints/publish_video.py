"""Generate and publish weekly horizontal videos."""

import asyncio
import datetime
from datetime import UTC
from pathlib import Path

from src.application.fetch_top_videos_use_case import FetchTopVideosRequest, FetchTopVideosUseCase
from src.application.workers.factory import WorkerFactory
from src.config.settings import AppSettings, get_app_settings
from src.domain.models import Platform, Release, ReleaseKind, TimeseriesRange, Video
from src.domain.services.video_metadata_service import generate_youtube_description, generate_youtube_title
from src.domain.utils import extract_video_hashtags
from src.infrastructure.storage.operational_metrics_repository import OperationalMetricsRepository
from src.infrastructure.storage.release_repository import ReleaseRepository
from src.infrastructure.storage.timeseries_repository import TimeSeriesRepository
from src.infrastructure.storage.video_repository import VideoRepository
from src.infrastructure.video.asset_manager import VideoAssetManager
from src.infrastructure.video.compositor import VideoCompositor
from src.infrastructure.video.downloader import VideoDownloader
from src.infrastructure.video.renderer import VideoRenderer
from src.infrastructure.video.thumbnail_generator import ThumbnailGenerator
from src.infrastructure.youtube.yt_client import YTClient
from src.infrastructure.youtube.yt_fake_client import YTClientFake
from src.shared.execution_lock import FileExecutionLock
from src.shared.logging import get_logger, setup_logging

logger = get_logger(__name__)


def _build_yt_client() -> YTClient:
    settings = get_app_settings()
    return YTClient() if settings.is_production_env else YTClientFake()


def _build_video_pipeline(video_downloader: VideoDownloader) -> tuple[VideoCompositor, ThumbnailGenerator]:
    settings = get_app_settings()
    asset_manager = VideoAssetManager(
        end_screen_file=settings.video_template_end_screen_file or "",
        start_screen_file=settings.video_template_start_screen_file or "",
        template_file=settings.video_template_file or "",
        template_vertical_file=settings.video_template_vertical_file or "",
        thumbnail_file=settings.video_template_thumbnail_file or "",
        thumbnail_font_file=settings.video_template_thumbnail_font_file or "",
        video_yt_resources_folder=video_downloader.video_yt_resources_folder,
        video_generated_base_folder=settings.video_generated_folder,
    )
    renderer = VideoRenderer(asset_manager)
    return VideoCompositor(asset_manager, renderer), ThumbnailGenerator(asset_manager)


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


async def _fetch_weekly_videos(*, day: datetime.date, db_timeseries_file: str, db_video_file: str) -> list[Video]:
    timeseries_repo = TimeSeriesRepository(db_timeseries_file)
    video_repo = VideoRepository(Path(db_video_file))
    fetch_videos_use_case = FetchTopVideosUseCase(timeseries_repo, video_repo)

    request = FetchTopVideosRequest(timeseries_range=TimeseriesRange.WEEKLY, day=day)
    result = await fetch_videos_use_case.execute(request)
    video_list = list(result.videos)
    video_list.sort(key=lambda x: (x.score is None, x.score if x.score is not None else 0), reverse=True)
    return video_list


async def _prepare_weekly_publish_assets(
    *,
    settings: AppSettings,
    video_list: list[Video],
) -> tuple[str, list[str], str, str, str]:
    logger.debug("start")
    downloader = VideoDownloader()
    await downloader.download_video(video_list)

    # with 0mq
    WorkerFactory().start_workers(video_list)

    compositor, thumbnail_generator = _build_video_pipeline(downloader)
    file_path = await compositor.join_processed_videos([video.video_id for video in video_list])

    hashtag_list = extract_video_hashtags(video_list)
    yt_title = generate_youtube_title(
        video_list=video_list,
        title_template=settings.yt_title_template,
        hashtags=hashtag_list,
    )
    logger.debug("generated title: ", yt_title=yt_title)

    yt_description = generate_youtube_description(
        video_list=video_list,
        description_template=settings.yt_description_template,
    )
    logger.debug("generated description:", yt_description=yt_description)

    thumbnail_path = await thumbnail_generator.generate_thumbnail(video_list[-4:])
    return file_path, hashtag_list, yt_title, yt_description, thumbnail_path


async def _upload_weekly_video(
    *,
    settings: AppSettings,
    file_path: str,
    yt_title: str,
    yt_description: str,
    thumbnail_path: str,
    hashtag_list: list[str],
) -> str | None:
    try:
        return await _build_yt_client().upload_video(
            video_path=file_path,
            title=yt_title,
            description=yt_description,
            thumbnail_path=thumbnail_path,
            playlist_id=settings.yt_playlist_id_weekly,
            tags=hashtag_list,
        )
    except Exception as exc:
        logger.exception("publish_video.youtube_upload_failed", error=str(exc))
        return None


def _persist_weekly_release(*, release_repo: ReleaseRepository, settings: AppSettings, yt_video_id: str) -> None:
    try:
        release_repo.add_or_update_release(
            Release(
                platform=Platform.YOUTUBE.value,
                client_id=settings.yt_auth_user_id,
                release_kind=ReleaseKind.WEEKLY_HORIZONTAL.value,
                release_id=yt_video_id,
                published_at=datetime.datetime.now(datetime.UTC).timestamp(),
            )
        )
    except Exception as exc:
        logger.exception("publish_video.release_persist_failed", error=str(exc))


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
        if release_repo.is_release_at_date(
            platform=Platform.YOUTUBE.value,
            release_date=day,
            release_kind=ReleaseKind.WEEKLY_HORIZONTAL.value,
        ):
            logger.info("publish_video.already_completed", day=str(day))
            metrics_repo.record_metric_event(stage="upload", is_error=False)
            return

        video_list = await _fetch_weekly_videos(
            day=day,
            db_timeseries_file=db_timeseries_file,
            db_video_file=db_video_file,
        )
        file_path, hashtag_list, yt_title, yt_description, thumbnail_path = await _prepare_weekly_publish_assets(
            settings=settings,
            video_list=video_list,
        )
        yt_video_id = await _upload_weekly_video(
            settings=settings,
            file_path=file_path,
            yt_title=yt_title,
            yt_description=yt_description,
            thumbnail_path=thumbnail_path,
            hashtag_list=hashtag_list,
        )
        if yt_video_id:
            _persist_weekly_release(
                release_repo=release_repo,
                settings=settings,
                yt_video_id=yt_video_id,
            )

        metrics_repo.record_metric_event(stage="upload", is_error=yt_video_id is None)
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
