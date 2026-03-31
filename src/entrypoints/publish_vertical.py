"""Generate and publish daily vertical videos."""

import asyncio
import datetime
from collections.abc import Sequence
from datetime import UTC
from pathlib import Path

from src.application.fetch_top_videos_use_case import FetchTopVideosRequest, FetchTopVideosUseCase
from src.application.publish_video_use_case import PublishVideoRequest, PublishVideoResult, PublishVideoUseCase
from src.application.workers.factory import WorkerFactory
from src.config.settings import AppSettings, get_app_settings
from src.domain.models import (
    CanonicalVideo,
    PublishingResult,
    Release,
    ReleaseKind,
    ReleasePlatform,
    TimeseriesRange,
    Video,
)
from src.domain.ports import VideoPublisher
from src.domain.utils import extract_video_hashtags
from src.infrastructure.publisher_registry import build_publishers
from src.infrastructure.social.spotify_client import SpotifyClient
from src.infrastructure.storage.release_repository import ReleaseRepository
from src.infrastructure.storage.timeseries_repository import TimeSeriesRepository
from src.infrastructure.storage.video_repository import VideoRepository
from src.infrastructure.video.asset_manager import VideoAssetManager
from src.infrastructure.video.compositor import VideoCompositor
from src.infrastructure.video.renderer import VideoRenderer
from src.infrastructure.youtube.downloader import VideoDownloader
from src.shared.execution_lock import FileExecutionLock
from src.shared.logging import get_logger, setup_logging

logger = get_logger(__name__)


def _build_video_compositor(video_downloader: VideoDownloader) -> VideoCompositor:
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
    return VideoCompositor(asset_manager, renderer)


def generate_yt_title(video_list: Sequence[Video], hashtag_list: list[str] | None = None) -> str:
    text_date = datetime.datetime.now(datetime.UTC).strftime("%d/%m/%Y")
    hashtags = " ".join(hashtag_list) if hashtag_list else ""
    return (
        get_app_settings()
        .yt_title_template.replace("@@TOP_DATE@@", f"[{text_date}] #top{len(video_list)}")
        .replace("@@HASHTAGS@@", f"\n{hashtags}")
    )


def generate_yt_description(video_list: Sequence[Video]) -> str:
    text_date = datetime.datetime.now(datetime.UTC).strftime("%d / %m / %Y")
    # Solo nombres válidos
    channels_names = list(
        {(video.channel.name if video.channel and video.channel.name else "") for video in video_list}
    )
    channels_names = [name for name in channels_names if name]
    original_publishers = ", ".join(channels_names)
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
        "Please note no copyright infringement is intended, and I do not own nor claim to own "
        "any of the original publishers recordings used in this video. "
        f"Original publishers : {original_publishers}."
    )
    disclaimer = f"------\nDisclaimer\n  - {legal_notice}\n\n  - {copyright_notice}\n\n  - {fair_use_text}\n------"

    video_list_names = ""
    for video in video_list:
        score = video.score if video.score is not None else "-"
        title = (
            video.yt_video_title_cleaned
            if hasattr(video, "yt_video_title_cleaned") and video.yt_video_title_cleaned
            else (video.title or "")
        )
        url = video.yt_video_url if hasattr(video, "yt_video_url") and video.yt_video_url else ""
        video_list_names += f"{score}.- {title} {url} \n"
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
    with FileExecutionLock(Path(settings.scheduler_lock_file), "vertical_publish") as execution_lock:
        if not execution_lock.acquired:
            return
        await _run_vertical_publish_job(settings)


def _pending_publishers(
    release_repo: ReleaseRepository,
    publishers: Sequence[VideoPublisher],
    day: datetime.date,
) -> list[VideoPublisher]:
    return [
        publisher
        for publisher in publishers
        if not release_repo.is_release_at_date(
            platform=publisher.platform_name.value,
            release_date=day,
            release_kind=ReleaseKind.DAILY_VERTICAL.value,
        )
    ]


def _is_spotify_release_pending(
    release_repo: ReleaseRepository,
    settings: AppSettings,
    day: datetime.date,
) -> bool:
    if not (settings.spotify_playlist_original and settings.is_spotify_configured):
        return False
    return not release_repo.is_release_at_date(
        platform=ReleasePlatform.SPOTIFY.value,
        release_date=day,
        release_kind=ReleaseKind.DAILY_VERTICAL.value,
    )


def _persist_spotify_release(release_repo: ReleaseRepository, settings: AppSettings) -> None:
    release_repo.add_or_update_release(
        Release(
            platform=ReleasePlatform.SPOTIFY.value,
            client_id=settings.spotify_user_id,
            release_kind=ReleaseKind.DAILY_VERTICAL.value,
            release_id=settings.spotify_playlist_original,
            published_at=datetime.datetime.now(datetime.UTC).timestamp(),
        )
    )


def _persist_publisher_release(
    release_repo: ReleaseRepository,
    settings: AppSettings,
    publisher: VideoPublisher,
    result: PublishingResult,
) -> None:
    release_repo.add_or_update_release(
        Release(
            platform=publisher.platform_name.name,
            client_id=_publisher_client_id(settings, publisher.platform_name.name),
            release_kind=ReleaseKind.DAILY_VERTICAL.value,
            release_id=result.published_id,
            published_at=result.published_at.timestamp()
            if result.published_at
            else datetime.datetime.now(datetime.UTC).timestamp(),
        )
    )


async def _load_daily_videos(
    timeseries_repo: TimeSeriesRepository,
    video_repo: VideoRepository,
    day: datetime.date,
) -> list[Video]:
    fetch_videos_use_case = FetchTopVideosUseCase(timeseries_repo, video_repo)
    request = FetchTopVideosRequest(timeseries_range=TimeseriesRange.DAILY, day=day)
    result = await fetch_videos_use_case.execute(request)
    return list(result.videos)


async def _maybe_update_spotify_original_playlist(
    settings: AppSettings,
    release_repo: ReleaseRepository,
    spotify_release_pending: bool,
    video_list: Sequence[Video],
) -> None:
    if not spotify_release_pending:
        return

    try:
        yt_video_title_list = [video.title.split("|")[0].strip() for video in video_list if video.title]
        await SpotifyClient().update_link_original_playlist(
            playlist_id=settings.spotify_playlist_original,
            song_title_list=yt_video_title_list,
        )
        _persist_spotify_release(release_repo, settings)
    except Exception as exc:
        logger.exception("publish_vertical.spotify_playlist_update_failed", error=str(exc))


def _video_to_canonical(video: Video) -> CanonicalVideo:
    return CanonicalVideo(
        video_id=video.video_id,
        title=video.title or "",
        channel_name=video.channel.name if video.channel and video.channel.name else "",
        views=video.views,
        views_growth=video.views_growth or 0,
        score=float(video.score) if video.score is not None else 0.0,
        score_previous=float(video.score_previous) if video.score_previous is not None else 0.0,
        thumbnail_url=video.yt_video_thumbnail_url if hasattr(video, "yt_video_thumbnail_url") else "",
    )


async def _publish_pending_vertical_videos(
    settings: AppSettings,
    release_repo: ReleaseRepository,
    pending_publishers: Sequence[VideoPublisher],
    video_list: Sequence[Video],
) -> None:
    selected_videos = list(video_list[:5])
    selected_videos.sort(
        key=lambda video: (video.score is None, video.score if video.score is not None else 0),
        reverse=True,
    )

    downloader = VideoDownloader()
    await downloader.download_video(selected_videos)
    WorkerFactory().start_vertical_workers(selected_videos)

    compositor = _build_video_compositor(downloader)
    file_path = await compositor.join_processed_videos(
        video_id_list=[video.video_id for video in selected_videos],
        vertical=True,
    )

    hashtag_list = extract_video_hashtags(selected_videos)
    yt_title = generate_yt_title(selected_videos, hashtag_list=hashtag_list)
    logger.debug("generated title: ", yt_title=yt_title)
    yt_description = generate_yt_description(selected_videos)
    logger.debug("generated description:", yt_description=yt_description)
    canonical_video_list = [_video_to_canonical(video) for video in selected_videos]

    async def _publish_one(publisher: VideoPublisher) -> PublishVideoResult:
        description = yt_description if publisher.platform_name.name == "YOUTUBE" else yt_title
        use_case = PublishVideoUseCase([publisher])
        return await use_case.execute(
            PublishVideoRequest(
                video_list=tuple(canonical_video_list),
                file_path=file_path,
                title=yt_title,
                description=description,
            )
        )

    async with asyncio.TaskGroup() as task_group:
        tasks = [(publisher, task_group.create_task(_publish_one(publisher))) for publisher in pending_publishers]

    for publisher, task in tasks:
        result = task.result().results[0]
        if not result.success:
            continue
        _persist_publisher_release(release_repo, settings, publisher, result)


async def _run_vertical_publish_job(settings: AppSettings) -> None:
    day = datetime.datetime.now(UTC).date()
    db_data_file = settings.db_data_file
    db_timeseries_file = settings.db_timeseries_file

    if not settings.is_production_env:
        db_data_file += ".test"
        db_timeseries_file += ".test"

    # Initialize repositories
    timeseries_repo = TimeSeriesRepository(db_timeseries_file)
    video_repo = VideoRepository(Path(db_data_file))
    release_repo = ReleaseRepository(db_data_file)
    publishers = build_publishers()
    pending_publishers = _pending_publishers(release_repo, publishers, day)
    spotify_release_pending = _is_spotify_release_pending(release_repo, settings, day)

    if not pending_publishers and not spotify_release_pending:
        logger.info("publish_vertical.already_completed", day=str(day))
        return

    video_list = await _load_daily_videos(timeseries_repo, video_repo, day)
    await _maybe_update_spotify_original_playlist(settings, release_repo, spotify_release_pending, video_list)

    if not pending_publishers:
        logger.info("publish_vertical.no_pending_publishers", day=str(day))
        return

    await _publish_pending_vertical_videos(settings, release_repo, pending_publishers, video_list)


def _publisher_client_id(settings: AppSettings, platform_name: str) -> str | None:
    if platform_name == ReleasePlatform.INSTAGRAM.value:
        return settings.instagram_client_username
    if platform_name == ReleasePlatform.TIKTOK.value:
        return settings.tiktok_user_openid
    return settings.yt_auth_user_id


def main() -> None:
    """Entry point for publish-vertical command."""
    settings = get_app_settings()
    setup_logging(settings.log_file_path)
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
