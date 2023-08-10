import asyncio
import datetime
from datetime import date

from src.db_client import DatabaseClient, Video, TimeseriesRange, video_list_mapper_hashtags
from src.logger import get_logger
from src.settings import get_app_settings
from src.tiktok_client import TikTokClient
from src.video_downloader import VideoDownloader
from src.video_processing import VideoProcessing
from src.worker_factory import WorkerFactory
from src.yt_client import get_yt_client

logger = get_logger(__name__)


async def generate_yt_title(video_list: list[Video], hashtag_list: list[str] = None) -> str:
    text_date = datetime.datetime.utcnow().strftime("%d/%m/%Y")
    hashtags = " ".join(hashtag_list) if hashtag_list else ""
    yt_title = (
        f"[{text_date}] #top{len(video_list)} #Bollywood #Songs #Today: Hottest Hits and Hidden Gems \n{hashtags}"
    )
    return yt_title


async def generate_yt_description(video_list: list[Video]) -> str:
    text_date = datetime.datetime.utcnow().strftime("%d / %m / %Y")
    yt_description = ""
    yt_description += f"""#Top{len(video_list)} Most Viewed Indian Songs
Last Day on Youtube India
{text_date} Trending Songs of the Day\n\n"""
    channels_names = list(set([video.channel.name for video in video_list]))

    for video in video_list:
        yt_description += f"{video.score}.- {video.yt_video_title_cleaned} {video.yt_video_url} \n"
        yt_description += f"© {video.channel.name}\n\n"

    yt_description += "\n\nPlease subscribe for more videos!\n"
    yt_description += "🔔 Turn on notifications so you don't miss a new video! 🔔\n\n"
    yt_description += "🙏Thanks For Watching🙏\n"
    yt_description += "🎶 SAT DEVA SINGH 🎶"
    yt_description += f"""
➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖
Disclaimer 
    · This publication and the information included in it are not intended to serve a substitute for consultation with an attonery.\n
    · Please note no copyright infringement is intended, and I do not own nor claim to own any of the original publishers recordings used in this video. Original publishers : {",".join(channels_names)}.\n 
    · As per the 3rd section of fair use guidelines borrowing small bits of material from an original work is more likely to be considered fair use. Copyright disclaimer under section 107 of the copyright act 1976, allowance is made for fair use\n
➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n\n
"""

    return yt_description


async def main():
    video_list = DatabaseClient().get_top_25_videos(timeseries_range=TimeseriesRange.DAILY, day=date.today())[:5]
    video_list.sort(key=lambda x: x.score, reverse=True)
    await VideoDownloader().download_video(video_list)

    # with 0mq
    WorkerFactory().start_vertical_workers(video_list)

    # file_path = "../videos/20230703_vertical_format.mp4"
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

    try:
        await TikTokClient().upload_video(
            video_path=file_path,
            title=yt_title,
        )
    except Exception as e:
        logger.error("Failed to upload TikTok", error=e)

    try:
        playlist_id = get_app_settings().yt_playlist_id_daily
        await get_yt_client().upload_video(
            video_path=file_path,
            title=yt_title,
            description=yt_description,
            thumbnail_path=None,
            playlist_id=playlist_id,
            tags=hashtag_list,
        )
    except Exception as e:
        logger.error("Failed to upload Youtube", error=e)

    await video_processor.delete_processed_videos()


if __name__ == "__main__":
    asyncio.run(main())
