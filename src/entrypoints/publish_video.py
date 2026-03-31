"""Generate and publish weekly horizontal videos."""

import asyncio
import datetime
from collections.abc import Sequence
from datetime import UTC
from pathlib import Path

from src.application.fetch_top_videos_use_case import FetchTopVideosRequest, FetchTopVideosUseCase
from src.application.workers.factory import WorkerFactory
from src.config.settings import AppSettings, get_app_settings
from src.domain.models import Release, ReleaseKind, ReleasePlatform, TimeseriesRange, Video
from src.domain.utils import extract_video_hashtags
from src.infrastructure.storage.release_repository import ReleaseRepository
from src.infrastructure.storage.timeseries_repository import TimeSeriesRepository
from src.infrastructure.video.asset_manager import VideoAssetManager
from src.infrastructure.video.compositor import VideoCompositor
from src.infrastructure.video.renderer import VideoRenderer
from src.infrastructure.video.thumbnail_generator import ThumbnailGenerator
from src.infrastructure.youtube import get_yt_client
from src.infrastructure.youtube.downloader import VideoDownloader
from src.shared.execution_lock import FileExecutionLock
from src.shared.logging import get_logger, setup_logging

logger = get_logger(__name__)


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


def generate_yt_title(video_list: Sequence[Video], hashtag_list: list[str] | None = None) -> str:
    text_date = datetime.datetime.now(datetime.UTC).strftime("%d/%m/%Y")
    hashtags = " ".join(hashtag_list) if hashtag_list else ""
    return (
        get_app_settings()
        .yt_title_template.replace("@@TOP_DATE@@", f"[{text_date}] #top{len(video_list)}")
        .replace("@@HASHTAGS@@", f"\n{hashtags}")
    )


def generate_yt_description(video_list: Sequence[Video]) -> str:
    text_date = datetime.datetime.now(datetime.UTC).strftime("%d/%m/%Y")
    channels_names = sorted({video.channel.name for video in video_list if video.channel and video.channel.name})
    original_publishers = ",".join(channels_names)
    fair_use_text = (
        "As per the 3rd section of fair use guidelines borrowing small bits of material from "
        "an original work is more likely to be considered fair use. Copyright disclaimer under "
        "section 107 of the copyright act 1976, allowance is made for fair use"
    )
    legal_notice = (
        "This publication and the information included in it are not intended to serve "
        "a substitute for consultation with an attonery."
    )
    copyright_notice = (
        "Please note no copyright infringement is intended, and I do not own nor claim "
        "to own any of the original publishers recordings used in this video. "
        f"Original publishers : {original_publishers}."
    )
    disclaimer = f"------\nDisclaimer\n  - {legal_notice}\n\n  - {copyright_notice}\n\n  - {fair_use_text}\n------"

    video_list_names = ""
    for video in video_list:
        video_list_names += f"{video.score}.- {video.yt_video_title_cleaned} {video.yt_video_url} \n"
        if video.channel and video.channel.name:
            video_list_names += f"© {video.channel.name}\n\n"

    return (
        get_app_settings()
        .yt_description_template.replace("@@TOP_DATE@@", f"{text_date} #top{len(video_list)}")
        .replace("@@VIDEO_LIST@@", f"{video_list_names}")
        .replace("@@DISCLAIMER@@", disclaimer)
    )


async def main_async() -> None:
    settings = get_app_settings()
    with FileExecutionLock(Path(settings.scheduler_lock_file), "weekly_publish") as execution_lock:
        if not execution_lock.acquired:
            return
        await _run_weekly_publish_job(settings)


async def _run_weekly_publish_job(settings: AppSettings) -> None:
    day = datetime.datetime.now(UTC).date()
    db_data_file = settings.db_data_file
    db_timeseries_file = settings.db_timeseries_file

    if not settings.is_production_env:
        db_data_file += ".test"
        db_timeseries_file += ".test"

    # Initialize repositories and use case
    timeseries_repo = TimeSeriesRepository(db_timeseries_file)
    release_repo = ReleaseRepository(db_data_file)
    if release_repo.is_release_at_date(
        platform=ReleasePlatform.YOUTUBE.value,
        release_date=day,
        release_kind=ReleaseKind.WEEKLY_HORIZONTAL.value,
    ):
        logger.info("publish_video.already_completed", day=str(day))
        return
    fetch_videos_use_case = FetchTopVideosUseCase(timeseries_repo)

    # Fetch top videos for the week
    request = FetchTopVideosRequest(timeseries_range=TimeseriesRange.WEEKLY, day=day)
    result = await fetch_videos_use_case.execute(request)
    video_list = list(result.videos)
    video_list.sort(key=lambda x: (x.score is None, x.score if x.score is not None else 0), reverse=True)

    logger.debug("start")
    downloader = VideoDownloader()
    await downloader.download_video(video_list)

    # with 0mq
    WorkerFactory().start_workers(video_list)

    compositor, thumbnail_generator = _build_video_pipeline(downloader)
    file_path = await compositor.join_processed_videos([video.video_id for video in video_list])

    yt_title = generate_yt_title(video_list)
    logger.debug("generated title: ", yt_title=yt_title)
    yt_description = generate_yt_description(video_list)
    logger.debug("generated description:", yt_description=yt_description)
    thumbnail_path = await thumbnail_generator.generate_thumbnail(video_list[-4:])
    hashtag_list = extract_video_hashtags(video_list)
    try:
        playlist_id = settings.yt_playlist_id_weekly

        yt_video_id = await get_yt_client().upload_video(
            video_path=file_path,
            title=yt_title,
            description=yt_description,
            thumbnail_path=thumbnail_path,
            playlist_id=playlist_id,
            tags=hashtag_list,
        )
    except Exception as exc:
        logger.exception("publish_video.youtube_upload_failed", error=str(exc))
        yt_video_id = None

    try:
        if yt_video_id:
            release_repo.add_or_update_release(
                Release(
                    platform=ReleasePlatform.YOUTUBE.value,
                    client_id=settings.yt_auth_user_id,
                    release_kind=ReleaseKind.WEEKLY_HORIZONTAL.value,
                    release_id=yt_video_id,
                    published_at=datetime.datetime.now(datetime.UTC).timestamp(),
                )
            )
    except Exception as exc:
        logger.exception("publish_video.release_persist_failed", error=str(exc))


def main() -> None:
    """Entry point for publish-video command."""
    settings = get_app_settings()
    setup_logging(settings.log_file_path)
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
