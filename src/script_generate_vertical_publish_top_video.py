import asyncio
import datetime
from datetime import date

from src.db_client import DatabaseClient, Release, ReleasePlatform, TimeseriesRange, Video, video_list_mapper_hashtags
from src.instagram_client import InstagramClient
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
    format_yt_title = get_app_settings().yt_title_template
    format_yt_title = format_yt_title.replace("@@TOP_DATE@@", f"[{text_date}] #top{len(video_list)}")
    format_yt_title = format_yt_title.replace("@@HASHTAGS@@", f"\n{hashtags}")
    return format_yt_title


async def generate_yt_description(video_list: list[Video]) -> str:
    text_date = datetime.datetime.utcnow().strftime("%d / %m / %Y")
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
        if video.channel:
            video_list_names += f"© {video.channel.name}\n\n"

    yt_description = get_app_settings().yt_description_template
    yt_description = yt_description.replace("@@TOP_DATE@@", f"{text_date} #top{len(video_list)}")
    yt_description = yt_description.replace("@@VIDEO_LIST@@", f"{video_list_names}")
    yt_description = yt_description.replace("@@DISCLAIMER@@", f"{disclaimer}")

    return yt_description


async def main():
    day = date.today()
    video_list = DatabaseClient().get_top_25_videos(timeseries_range=TimeseriesRange.DAILY, day=day)

    try:
        yt_video_title_list = [video.title.split("|")[0].strip() for video in video_list]
        await SpotifyClient().update_link_original_playlist(
            playlist_id=get_app_settings().spotify_playlist_original,
            song_title_list=yt_video_title_list,
        )
    except Exception as e:
        logger.error("Failed to update Spotify original playlist", error=e)

    yt_video_id_list = [video.video_id for video in video_list]
    video_list = video_list[:5]
    video_list.sort(key=lambda x: x.score, reverse=True)
    await VideoDownloader().download_video(video_list)

    # with 0mq
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

    await publish_instagram(file_path=file_path, yt_title=yt_title)
    await publish_tiktok(file_path=file_path, yt_title=yt_title)
    await publish_yt(
        file_path=file_path,
        yt_title=yt_title,
        yt_description=yt_description,
        yt_video_id_list=yt_video_id_list,
        hashtag_list=hashtag_list,
    )

    # await video_processor.delete_processed_videos()


async def publish_instagram(file_path: str, yt_title: str):
    try:
        instagram_publish_video_id = await InstagramClient().upload_video(
            video_path=file_path,
            caption=yt_title,
        )
    except Exception as e:
        logger.error("Failed to upload Instagram", error=e)
        instagram_publish_video_id = None

    try:
        DatabaseClient().add_or_update_release(
            release=Release(
                platform=ReleasePlatform.INSTAGRAM.value,
                client_id=get_app_settings().instagram_client_username,
                release_id=instagram_publish_video_id,
                published_at=datetime.datetime.now().timestamp(),
            )
        )
    except Exception as e:
        logger.error("Failed to save Instagram Release", error=e)


async def publish_tiktok(
    file_path: str,
    yt_title: str,
) -> None:
    try:
        tiktok_publish_video_id = await TikTokClient().upload_video(
            video_path=file_path,
            title=yt_title,
        )
    except Exception as e:
        logger.error("Failed to upload TikTok", error=e)
        tiktok_publish_video_id = None

    try:
        DatabaseClient().add_or_update_release(
            release=Release(
                platform=ReleasePlatform.TIKTOK.value,
                client_id=get_app_settings().tiktok_user_openid,
                release_id=tiktok_publish_video_id,
                published_at=datetime.datetime.now().timestamp(),
            )
        )
    except Exception as e:
        logger.error("Failed to save TikTok Release", error=e)


async def publish_yt(
    file_path: str,
    yt_title: str,
    yt_description: str,
    yt_video_id_list: list[str],
    hashtag_list: list[str],
) -> None:
    try:
        playlist_id = get_app_settings().yt_playlist_id_daily
        yt_video_id = await get_yt_client().upload_video(
            video_path=file_path,
            title=yt_title,
            description=yt_description,
            thumbnail_path=None,
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

    try:
        await get_yt_client().update_link_original_playlist(
            playlist_id=get_app_settings().yt_playlist_id_links_original,
            yt_video_id_list=yt_video_id_list,
        )
    except Exception as e:
        logger.error("Failed to update YT original playlist", error=e)


if __name__ == "__main__":
    asyncio.run(main())
