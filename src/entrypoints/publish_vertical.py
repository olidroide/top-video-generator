"""Generate and publish daily vertical videos."""

import asyncio
import datetime
from datetime import date

from src.db_client import DatabaseClient, Release, ReleasePlatform, TimeseriesRange, Video, video_list_mapper_hashtags
from src.infrastructure.publisher_registry import build_publishers
from src.logger import get_logger
from src.settings import get_app_settings
from src.spotify_client import SpotifyClient
from src.video_downloader import VideoDownloader
from src.video_processing import VideoProcessing
from src.worker_factory import WorkerFactory

logger = get_logger(__name__)


async def generate_yt_title(video_list: list[Video], hashtag_list: list[str] = []) -> str:
    text_date = datetime.datetime.now(datetime.UTC).strftime("%d/%m/%Y")
    hashtags = " ".join(hashtag_list) if hashtag_list else ""
    format_yt_title = get_app_settings().yt_title_template
    format_yt_title = format_yt_title.replace("@@TOP_DATE@@", f"[{text_date}] #top{len(video_list)}")
    format_yt_title = format_yt_title.replace("@@HASHTAGS@@", f"\n{hashtags}")
    return format_yt_title


async def generate_yt_description(video_list: list[Video]) -> str:
    text_date = datetime.datetime.now(datetime.UTC).strftime("%d / %m / %Y")
    # Solo nombres válidos
    channels_names = list(
        {(video.channel.name if video.channel and video.channel.name else "") for video in video_list}
    )
    channels_names = [name for name in channels_names if name]
    disclaimer = f"""
➖➖➖➖➖➖
Disclaimer 
  · This publication and the information included in it are not intended to serve a substitute for consultation with an attonery.\n
  · Please note no copyright infringement is intended, and I do not own nor claim to own any of the original publishers recordings used in this video. Original publishers : {", ".join(channels_names)}.\n 
  · As per the 3rd section of fair use guidelines borrowing small bits of material from an original work is more likely to be considered fair use. Copyright disclaimer under section 107 of the copyright act 1976, allowance is made for fair use\n
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
    db = DatabaseClient()
    # Idempotency guard
    already_published = all(
        db.is_release_at_date(release_platform=platform, release_date=day)
        for platform in (
            ReleasePlatform.YT,
            ReleasePlatform.INSTAGRAM,
            ReleasePlatform.TIKTOK,
        )
    )
    if already_published:
        logger.info("vertical video already published today on all platforms, exiting early")
        return

    video_list = db.get_top_25_videos(timeseries_range=TimeseriesRange.DAILY, day=day)

    try:
        yt_video_title_list = [video.title.split("|")[0].strip() for video in video_list if video.title]
        await SpotifyClient().update_link_original_playlist(
            playlist_id=get_app_settings().spotify_playlist_original,
            song_title_list=yt_video_title_list,
        )
    except Exception as e:
        logger.error("Failed to update Spotify original playlist", error=e)

    yt_video_id_list = [video.video_id for video in video_list]

    video_list = video_list[:5]
    # sort: score None al final
    video_list.sort(key=lambda x: (x.score is None, x.score if x.score is not None else 0), reverse=True)
    await VideoDownloader().download_video(video_list)
    WorkerFactory().start_vertical_workers(video_list)

    video_processor = VideoProcessing()
    file_path = await video_processor.join_processed_videos(
        video_id_list=[video.video_id for video in video_list],
        vertical=True,
    )

    hashtag_list = video_list_mapper_hashtags(video_list)
    yt_title = await generate_yt_title(video_list, hashtag_list=hashtag_list)
    logger.debug("generated title: ", yt_title=yt_title)
    yt_description = await generate_yt_description(video_list)
    logger.debug("generated description:", yt_description=yt_description)

    # Hexagonal: convertir Video → CanonicalVideo para adapters
    from src.domain.models import CanonicalVideo, VideoScoreStatus

    def video_to_canonical(v):
        return CanonicalVideo(
            video_id=v.video_id,
            title=v.title or "",
            channel_name=v.channel.name if v.channel and v.channel.name else "",
            views=v.views,
            views_growth=v.views_growth or 0,
            score=float(v.score) if v.score is not None else 0.0,
            score_previous=float(v.score_previous) if v.score_previous is not None else 0.0,
            score_status=VideoScoreStatus(v.score_status) if v.score_status else VideoScoreStatus.NEW,
            thumbnail_url=v.yt_video_thumbnail_url if hasattr(v, "yt_video_thumbnail_url") else "",
        )

    canonical_video_list = [video_to_canonical(v) for v in video_list]

    publishers = build_publishers()
    results = []
    async with asyncio.TaskGroup() as tg:
        tasks = []
        for publisher in publishers:
            desc = yt_description if publisher.platform_name.name == "YOUTUBE" else yt_title
            task = tg.create_task(
                publisher.publish_video(
                    video_list=canonical_video_list,
                    file_path=file_path,
                    title=yt_title,
                    description=desc,
                )
            )
            tasks.append((publisher, task))
        for publisher, task in tasks:
            result = await task
            results.append(result)
            db.add_or_update_release(
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

    # await video_processor.delete_processed_videos()

    # Nota: la actualización de playlist de YouTube original debe hacerse aparte si es necesario


def main():
    """Entry point for publish-vertical command."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
