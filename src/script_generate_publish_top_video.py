import asyncio
import datetime
from datetime import date, timezone

from src.db_client import DatabaseClient, Release, ReleasePlatform, TimeseriesRange, Video, video_list_mapper_hashtags
from src.logger import get_logger
from src.settings import get_app_settings
from src.video_downloader import VideoDownloader
from src.video_processing import VideoProcessing
from src.worker_factory import WorkerFactory
from src.yt_client import get_yt_client

logger = get_logger(__name__)


async def generate_yt_title(video_list: list[Video], hashtag_list: list[str] = None) -> str:
    text_date = datetime.datetime.now(timezone.utc).strftime("%d/%m/%Y")
    hashtags = " ".join(hashtag_list) if hashtag_list else ""
    format_yt_title = get_app_settings().yt_title_template
    format_yt_title = format_yt_title.replace("@@TOP_DATE@@", f"[{text_date}] #top{len(video_list)}")
    format_yt_title = format_yt_title.replace("@@HASHTAGS@@", f"\n{hashtags}")
    return format_yt_title


async def generate_yt_description(video_list: list[Video]) -> str:
    text_date = datetime.datetime.now(timezone.utc).strftime("%d/%m/%Y")
    channels_names = list(set([video.channel.name for video in video_list]))
    disclaimer = f"""
➖➖➖➖➖➖
Disclaimer 
  · This publication and the information included in it are not intended to serve a substitute for consultation with an attonery.\n
  · Please note no copyright infringement is intended, and I do not own nor claim to own any of the original publishers recordings used in this video. Original publishers : {",".join(channels_names)}.\n 
  · As per the 3rd section of fair use guidelines borrowing small bits of material from an original work is more likely to be considered fair use. Copyright disclaimer under section 107 of the copyright act 1976, allowance is made for fair use\n
➖➖➖➖➖➖
    """

    video_list_names = ""
    for video in video_list:
        video_list_names += f"{video.score}.- {video.yt_video_title_cleaned} {video.yt_video_url} \n"
        video_list_names += f"© {video.channel.name}\n\n"

    yt_description = get_app_settings().yt_description_template
    yt_description = yt_description.replace("@@TOP_DATE@@", f"{text_date} #top{len(video_list)}")
    yt_description = yt_description.replace("@@VIDEO_LIST@@", f"{video_list_names}")
    yt_description = yt_description.replace("@@DISCLAIMER@@", f"{disclaimer}")

    return yt_description


async def main():
    video_list = DatabaseClient().get_top_25_videos(timeseries_range=TimeseriesRange.WEEKLY, day=date.today())
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
    hashtag_list = video_list_mapper_hashtags(video_list)
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
        DatabaseClient().add_or_update_release(
            release=Release(
                platform=ReleasePlatform.YT.value,
                client_id=get_app_settings().yt_auth_user_id,
                release_id=yt_video_id,
                published_at=datetime.datetime.now().timestamp(),
            )
        )
    except Exception as e:
        logger.error("Failed to save Youtube Release", error=e)

    # await video_processor.delete_processed_videos()


if __name__ == "__main__":
    asyncio.run(main())
