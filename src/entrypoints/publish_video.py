"""Generate and publish weekly horizontal videos."""

import asyncio
import datetime
from datetime import date

from src.application.fetch_top_videos_use_case import FetchTopVideosRequest, FetchTopVideosUseCase
from src.application.workers.factory import WorkerFactory
from src.config.settings import get_app_settings
from src.domain.models import Release, ReleasePlatform, TimeseriesRange
from src.domain.utils import extract_video_hashtags
from src.infrastructure.storage.release_repository import ReleaseRepository
from src.infrastructure.storage.timeseries_repository import TimeSeriesRepository
from src.infrastructure.youtube import get_yt_client
from src.infrastructure.youtube.downloader import VideoDownloader
from src.shared.logging import get_logger
from src.video_processing import VideoProcessing

logger = get_logger(__name__)


async def generate_yt_title(video_list, hashtag_list: list[str] | None = None) -> str:
    text_date = datetime.datetime.now(datetime.UTC).strftime("%d/%m/%Y")
    hashtags = " ".join(hashtag_list) if hashtag_list else ""
    format_yt_title = get_app_settings().yt_title_template
    format_yt_title = format_yt_title.replace("@@TOP_DATE@@", f"[{text_date}] #top{len(video_list)}")
    format_yt_title = format_yt_title.replace("@@HASHTAGS@@", f"\n{hashtags}")
    return format_yt_title


async def generate_yt_description(video_list) -> str:
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
        video_list_names += f"{video.score}.- {video.yt_video_title_cleaned} {video.yt_video_url} \n"
        if video.channel and video.channel.name:
            video_list_names += f"© {video.channel.name}\n\n"

    yt_description = get_app_settings().yt_description_template
    yt_description = yt_description.replace("@@TOP_DATE@@", f"{text_date} #top{len(video_list)}")
    yt_description = yt_description.replace("@@VIDEO_LIST@@", f"{video_list_names}")
    yt_description = yt_description.replace("@@DISCLAIMER@@", f"{disclaimer}")

    return yt_description


async def main_async():
    settings = get_app_settings()
    db_data_file = settings.db_data_file
    db_timeseries_file = settings.db_timeseries_file

    if not settings.is_production_env:
        db_data_file += ".test"
        db_timeseries_file += ".test"

    # Initialize repositories and use case
    timeseries_repo = TimeSeriesRepository(db_timeseries_file)
    release_repo = ReleaseRepository(db_data_file)
    fetch_videos_use_case = FetchTopVideosUseCase(timeseries_repo)

    # Fetch top videos for the week
    request = FetchTopVideosRequest(timeseries_range=TimeseriesRange.WEEKLY, day=date.today())
    result = await fetch_videos_use_case.execute(request)
    video_list = list(result.videos)
    video_list.sort(key=lambda x: x.score, reverse=True)

    logger.debug("start")
    await VideoDownloader().download_video(video_list)

    # with 0mq
    WorkerFactory().start_workers(video_list)
    # await VideoProcessing().post_process_video(video_list[0])

    video_processor = VideoProcessing()
    file_path = await video_processor.join_processed_videos([video.video_id for video in video_list])

    # file_path = "../videos/20230630_format.mp4"
    yt_title = await generate_yt_title(video_list)
    logger.debug("generated title: ", yt_title=yt_title)
    yt_description = await generate_yt_description(video_list)
    logger.debug("generated description:", yt_description=yt_description)
    thumbnail_path = await video_processor.generate_thumbnail(video_list[-4:])
    hashtag_list = extract_video_hashtags(video_list)
    try:
        playlist_id = get_app_settings().yt_playlist_id_daily

        yt_video_id = await get_yt_client().upload_video(
            video_path=file_path,
            title=yt_title,
            description=yt_description,
            thumbnail_path=thumbnail_path,
            playlist_id=playlist_id,
            tags=hashtag_list,
        )
    except Exception as e:
        logger.error("Failed to upload Youtube", error=e)
        yt_video_id = None

    try:
        release_repo.add_or_update_release(
            Release(
                platform=ReleasePlatform.YOUTUBE.value,
                client_id=get_app_settings().yt_auth_user_id,
                release_id=yt_video_id,
                published_at=datetime.datetime.now(datetime.UTC).timestamp(),
            )
        )
    except Exception as e:
        logger.error("Failed to save Youtube Release", error=e)

    # await video_processor.delete_processed_videos()


def main():
    """Entry point for publish-video command."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
