import asyncio
from datetime import datetime, timezone

import isodate
from src.logger import get_logger

from src.db_client import DatabaseClient, Video, VideoPoint, Channel, VideoPointTools
from src.yt_client import get_yt_client

logger = get_logger(__name__)


async def is_passed_enough_time_from_last_fetch(
    db_client: DatabaseClient,
    min_days: int = 1,
) -> bool:
    if not (last_timeseries_datetime := db_client.get_last_timeseries_datetime()):
        logger.debug("No timeseries found")
        return True
    last_timeseries_datetime = last_timeseries_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
    current_datetime = datetime.utcnow().astimezone(timezone.utc)
    delta_from_last_recollection = current_datetime - last_timeseries_datetime

    if not (is_enough_time := delta_from_last_recollection.days >= min_days):
        logger.debug(f"Less than a {min_days} days ({delta_from_last_recollection}) to recollect data")
    return is_enough_time


async def main():
    start_process_datetime = datetime.utcnow().astimezone(timezone.utc)
    db_client = DatabaseClient()
    if not await is_passed_enough_time_from_last_fetch(db_client=db_client):
        return

    yt_client = get_yt_client()

    # last_timeseries_videos_fetched: dict[str, VideoPoint] = {
    #     video_point.video_id: video_point for video_point in db_client.get_last_timeseries_videos()
    # }
    last_timeseries_videos_fetched: list[VideoPoint] = list(db_client.get_last_timeseries_videos())

    current_timeseries_videos_fetched: list[VideoPoint] = []

    popular_videos_result = await yt_client.get_popular_videos()
    video_id_list = [video.id for video in popular_videos_result.items]
    for video_id in video_id_list:
        video_details = await yt_client.get_video_details(video_id)
        video_item = video_details.items.pop()
        logger.debug("video details", video_details=video_item)
        duration = isodate.parse_duration(video_item.contentDetails.duration)

        db_client.add_or_update_video(
            video=Video(
                video_id=video_item.id,
                views=video_item.statistics.viewCount,
                likes=video_item.statistics.likeCount,
                title=video_item.snippet.title,
                description=video_item.snippet.description,
                duration=duration.total_seconds(),
                channel=Channel(
                    channel_id=video_item.snippet.channelId,
                    name=video_item.snippet.channelTitle,
                ),
            )
        )

        last_video_point = VideoPoint(
            time=start_process_datetime,
            video_id=video_item.id,
            views=video_item.statistics.viewCount,
            likes=video_item.statistics.likeCount,
        )

        # last_video_point.views_growth = VideoPointTools.calculate_view_growth(
        #     last_video=last_video_point,
        #     previous_video=last_timeseries_videos_fetched.get(video_item.id),
        # )
        current_timeseries_videos_fetched.append(last_video_point)

    # if len(current_timeseries_videos_fetched) != len(video_id_list):
    #     raise Exception("required same yt fetched size than processed")
    #
    # current_timeseries_videos_fetched.sort(key=lambda x: x.views_growth, reverse=True)
    # for index, video_point in enumerate(current_timeseries_videos_fetched):
    #     video_point.score = index + 1
    #     previous_video = last_timeseries_videos_fetched.get(video_point.video_id)
    #     video_point.score_status = VideoPointTools.map_score_video_score_status(
    #         current_score=video_point.score,
    #         previous_score=previous_video.score if previous_video else None,
    #     )

    for video_point in VideoPointTools.generate_top_list_compared(
        current_video_list=current_timeseries_videos_fetched,
        previous_video_list=last_timeseries_videos_fetched,
    ):
        db_client.add_video_point(video_point=video_point)

    logger.info("Finish fetch YT Data", current_timeseries_videos_fetched=current_timeseries_videos_fetched)
    # get_video_visualizations(db_client=db_client)


if __name__ == "__main__":
    asyncio.run(main())
