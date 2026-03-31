"""Generate and publish daily vertical videos."""

import asyncio
import datetime
from collections.abc import Sequence
from datetime import date

from src.application.fetch_top_videos_use_case import FetchTopVideosRequest, FetchTopVideosUseCase
from src.application.publish_video_use_case import PublishVideoRequest, PublishVideoUseCase
from src.application.workers.factory import WorkerFactory
from src.config.settings import get_app_settings
from src.domain.models import CanonicalVideo, Release, ReleasePlatform, TimeseriesRange, Video
from src.domain.utils import extract_video_hashtags
from src.infrastructure.publisher_registry import build_publishers
from src.infrastructure.social.spotify_client import SpotifyClient
from src.infrastructure.storage.release_repository import ReleaseRepository
from src.infrastructure.storage.timeseries_repository import TimeSeriesRepository
from src.infrastructure.video.asset_manager import VideoAssetManager
from src.infrastructure.video.compositor import VideoCompositor
from src.infrastructure.video.renderer import VideoRenderer
from src.infrastructure.youtube.downloader import VideoDownloader
from src.shared.logging import get_logger

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
    format_yt_title = get_app_settings().yt_title_template
    format_yt_title = format_yt_title.replace("@@TOP_DATE@@", f"[{text_date}] #top{len(video_list)}")
    format_yt_title = format_yt_title.replace("@@HASHTAGS@@", f"\n{hashtags}")
    return format_yt_title


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
    disclaimer = f"""
➖➖➖➖➖➖
Disclaimer 
  · {legal_notice}\n
  · {copyright_notice}\n 
  · {fair_use_text}\n
➖➖➖➖➖➖
    """

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

    yt_description = get_app_settings().yt_description_template
    yt_description = yt_description.replace("@@TOP_DATE@@", f"{text_date} #top{len(video_list)}")
    yt_description = yt_description.replace("@@VIDEO_LIST@@", f"{video_list_names}")
    yt_description = yt_description.replace("@@DISCLAIMER@@", f"{disclaimer}")

    return yt_description


async def main_async():
    day = date.today()
    settings = get_app_settings()
    db_data_file = settings.db_data_file
    db_timeseries_file = settings.db_timeseries_file

    if not settings.is_production_env:
        db_data_file += ".test"
        db_timeseries_file += ".test"

    # Initialize repositories
    timeseries_repo = TimeSeriesRepository(db_timeseries_file)
    release_repo = ReleaseRepository(db_data_file)

    # Idempotency guard
    already_published = all(
        release_repo.is_release_at_date(platform=platform.value, release_date=day) for platform in ReleasePlatform
    )
    if already_published:
        logger.info("vertical video already published today on all platforms, exiting early")
        return

    # Fetch top videos for today
    fetch_videos_use_case = FetchTopVideosUseCase(timeseries_repo)
    request = FetchTopVideosRequest(timeseries_range=TimeseriesRange.DAILY, day=day)
    result = await fetch_videos_use_case.execute(request)
    video_list = list(result.videos)

    try:
        yt_video_title_list = [video.title.split("|")[0].strip() for video in video_list if video.title]
        await SpotifyClient().update_link_original_playlist(
            playlist_id=get_app_settings().spotify_playlist_original,
            song_title_list=yt_video_title_list,
        )
    except Exception as e:
        logger.error("Failed to update Spotify original playlist", error=e)

    video_list = video_list[:5]
    # sort: score None al final
    video_list.sort(key=lambda x: (x.score is None, x.score if x.score is not None else 0), reverse=True)
    downloader = VideoDownloader()
    await downloader.download_video(video_list)
    WorkerFactory().start_vertical_workers(video_list)

    compositor = _build_video_compositor(downloader)
    file_path = await compositor.join_processed_videos(
        video_id_list=[video.video_id for video in video_list],
        vertical=True,
    )

    hashtag_list = extract_video_hashtags(video_list)
    yt_title = generate_yt_title(video_list, hashtag_list=hashtag_list)
    logger.debug("generated title: ", yt_title=yt_title)
    yt_description = generate_yt_description(video_list)
    logger.debug("generated description:", yt_description=yt_description)

    # Hexagonal: convertir Video → CanonicalVideo para adapters
    def video_to_canonical(v) -> CanonicalVideo:
        return CanonicalVideo(
            video_id=v.video_id,
            title=v.title or "",
            channel_name=v.channel.name if v.channel and v.channel.name else "",
            views=v.views,
            views_growth=v.views_growth or 0,
            score=float(v.score) if v.score is not None else 0.0,
            score_previous=float(v.score_previous) if v.score_previous is not None else 0.0,
            thumbnail_url=v.yt_video_thumbnail_url if hasattr(v, "yt_video_thumbnail_url") else "",
        )

    canonical_video_list = [video_to_canonical(v) for v in video_list]

    publishers = build_publishers()
    results = []

    async def _publish_one(publisher):
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

    async with asyncio.TaskGroup() as tg:
        tasks = []
        for publisher in publishers:
            task = tg.create_task(_publish_one(publisher))
            tasks.append((publisher, task))
        for publisher, task in tasks:
            use_case_result = await task
            result = use_case_result.results[0]
            results.append(result)
            release_repo.add_or_update_release(
                Release(
                    platform=publisher.platform_name.name,
                    client_id=get_app_settings().instagram_client_username
                    if publisher.platform_name.name == "INSTAGRAM"
                    else (
                        get_app_settings().tiktok_user_openid
                        if publisher.platform_name.name == "TIKTOK"
                        else get_app_settings().yt_auth_user_id
                    ),
                    release_id=result.published_id,
                    published_at=result.published_at.timestamp()
                    if result.published_at
                    else datetime.datetime.now(datetime.UTC).timestamp(),
                )
            )

    # Nota: la actualización de playlist de YouTube original debe hacerse aparte si es necesario


def main():
    """Entry point for publish-vertical command."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
