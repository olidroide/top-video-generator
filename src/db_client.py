import re
from abc import abstractmethod
from datetime import datetime, timezone, timedelta, date
from enum import Enum
from typing import Iterator

from pydantic import BaseModel, PastDate
from tinydb import TinyDB, Query
from tinyflux import TinyFlux, Point, TagQuery, TimeQuery

from src.logger import get_logger
from src.settings import get_app_settings

logger = get_logger(__name__)


class TikTokAuth(BaseModel):
    token: str | None
    refresh_token: str | None
    client_id: str | None
    scopes: list[str] | None


class YtAuth(BaseModel):
    token: str | None
    refresh_token: str | None
    token_uri: str | None
    client_id: str | None
    client_secret: str | None
    scopes: list[str] | None


class ReleasePlatform(str, Enum):
    YT = "YT"
    TIKTOK = "TIKTOK"


class Release(BaseModel):
    platform: str | None  # ReleasePlatform
    client_id: str | None
    release_id: str | None
    published_at: float | None


class VideoScoreStatus(str, Enum):
    UP = "UP"
    DOWN = "DOWN"
    NEW = "NEW"
    EQUAL = "EQUAL"


class TimePoint(BaseModel):
    time: datetime


class Channel(BaseModel):
    channel_id: str | None
    name: str | None


class Video(BaseModel):
    video_id: str
    views: int = 0
    likes: int = 0
    views_growth: int | None
    score: int | None
    score_status: VideoScoreStatus | None
    score_previous: int | None
    title: str | None
    description: str | None
    channel: Channel | None
    duration: int | None

    @property
    def hashtags_in_description(self) -> list[str]:
        regex = "#(\w+)"
        hashtag_list = re.findall(regex, self.description)
        return [f"#{hashtag}" for hashtag in hashtag_list]

    @property
    def yt_video_thumbnail_url(self) -> str:
        return f"https://i.ytimg.com/vi/{self.video_id}/maxresdefault.jpg"

    @property
    def yt_video_url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"

    @property
    def yt_video_title_cleaned(self) -> str:
        return (
            self.title.replace("(Video)", "")
            .replace("(Music Video)", "")
            .replace("Official Video", "")
            .replace("#Video", "")
            .replace("Full Video", "")
            .replace("(video)", "")
            .replace("Full Song", "")
            .replace(" - ", " ")
            .replace("()", "")
            .replace("( )", "")
            .replace("(Full )", "")
            .replace(": ", " ")
            .replace("  ", " ")
            .strip()
        )


class VideoPoint(Video, TimePoint):
    pass


class TimeseriesRange(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"


class VideoPointTools:
    @staticmethod
    def calculate_view_growth(last_video: VideoPoint, previous_video: VideoPoint | None) -> int:
        if not previous_video:
            return last_video.views

        return abs(last_video.views - previous_video.views)

    @staticmethod
    def map_score_video_score_status(current_score=None, previous_score=None) -> VideoScoreStatus:
        score_status = None
        if not previous_score:
            score_status = VideoScoreStatus.NEW
        elif current_score == previous_score:
            score_status = VideoScoreStatus.EQUAL
        elif current_score < previous_score:
            score_status = VideoScoreStatus.UP
        elif current_score > previous_score:
            score_status = VideoScoreStatus.DOWN

        return score_status

    @staticmethod
    def calculate_datetime_for_range(
        timeseries_range: TimeseriesRange,
        day: PastDate = date.today(),
    ) -> datetime:
        map_timeseries_range_days = {
            TimeseriesRange.DAILY: 1,
            TimeseriesRange.WEEKLY: 7,
        }
        from_days_ago = map_timeseries_range_days.get(timeseries_range, 7)

        from_datetime = datetime.combine(day, datetime.min.time())
        return from_datetime - timedelta(days=from_days_ago)

    @staticmethod
    def generate_top_list_compared(
        current_video_list: list[VideoPoint],
        previous_video_list: list[VideoPoint],
    ) -> list[VideoPoint]:
        map_previous_video_list_by_id = {video_point.video_id: video_point for video_point in previous_video_list}

        for video_point in current_video_list:
            previous_video = map_previous_video_list_by_id.get(video_point.video_id)
            video_point.views_growth = (
                VideoPointTools.calculate_view_growth(video_point, previous_video)
                if previous_video
                else video_point.views_growth or video_point.views
            )

        current_video_list.sort(key=lambda x: x.views_growth, reverse=True)

        for index, video_point in enumerate(current_video_list):
            video_point.score = index + 1
            previous_video = map_previous_video_list_by_id.get(video_point.video_id)
            video_point.score_previous = previous_video.score if previous_video else None
            video_point.score_status = (
                VideoPointTools.map_score_video_score_status(
                    current_score=video_point.score,
                    previous_score=video_point.score_previous,
                )
                if previous_video_list
                else video_point.score_status
            )
            video_point.score_status = video_point.score_status if video_point.score_status else VideoScoreStatus.NEW

        return current_video_list


class DatabaseClient:
    def __init__(self) -> None:
        super().__init__()
        settings = get_app_settings()
        db_timeseries_file = settings.db_timeseries_file
        db_data_file = settings.db_data_file
        if not settings.is_production_env:
            db_timeseries_file += ".test"
            db_data_file += ".test"

        self._db = TinyFlux(db_timeseries_file)
        self._tiny_db = TinyDB(db_data_file)

    @abstractmethod
    def _get_timeseries_range(self) -> str:
        pass

    def add_video_point(
        self,
        video_point: VideoPoint,
    ):
        self._db.insert(
            Point(
                measurement="Video visualizations",
                time=video_point.time,  # datetime.fromisoformat("2020-08-28T00:00:00-07:00"),
                tags={
                    "video_id": video_point.video_id,
                    "score_status": video_point.score_status.value,
                },
                fields={
                    "views": video_point.views,
                    "likes": video_point.likes,
                    "views_growth": video_point.views_growth,
                    "score": video_point.score,
                },
            )
        )

    def add_or_update_video(
        self,
        video: Video,
    ) -> Video:
        if self.get_video(video.video_id):
            return self.update_video(video)

        table_video = self._tiny_db.table("video")
        table_video.insert(video.dict())
        return video

    def update_video(
        self,
        video: Video,
    ) -> Video | None:
        table_video = self._tiny_db.table("video")
        table_video.update(video.dict(), Query().video_id == video.video_id)
        return video

    def get_video(
        self,
        video_id: str,
    ) -> Video | None:
        table_video = self._tiny_db.table("video")
        if not (results := table_video.search(Query().video_id == video_id)):
            return None

        return Video.parse_obj(results[0])

    def search_video(
        self,
        video_id: str = None,
    ) -> list[Video]:
        table_video = self._tiny_db.table("video")
        results = table_video.search(Query().video_id.matches(video_id, flags=re.IGNORECASE))
        # results = table_video.search(Query().video_id.search("b+"))
        return [Video.parse_obj(result) for result in results]

    def update_video_point(
        self,
        video_point: VideoPoint,
    ):
        query = (TagQuery().video_id == video_point.video_id) & (
            TimeQuery() == video_point.time.astimezone(timezone.utc)
        )
        self._db.update(
            query,
            tags={
                "score_status": video_point.score_status.value,
            },
            fields={
                "views_growth": video_point.views_growth,
                "score": video_point.score,
            },
        )

    def get_tiktok_auth(
        self,
        client_id: str,
    ) -> TikTokAuth | None:
        table_tiktok = self._tiny_db.table("tiktok_auth")
        if not (results := table_tiktok.search(Query().client_id == client_id)):
            return None

        return TikTokAuth.parse_obj(results[0])

    def update_tiktok_auth(
        self,
        tiktok_auth: TikTokAuth,
    ) -> TikTokAuth | None:
        table_tiktok = self._tiny_db.table("tiktok_auth")
        table_tiktok.update(tiktok_auth.dict(), Query().client_id == tiktok_auth.client_id)
        return tiktok_auth

    def add_or_update_tiktok_auth(
        self,
        tiktok_auth: TikTokAuth,
    ) -> TikTokAuth:
        if self.get_tiktok_auth(tiktok_auth.client_id):
            return self.update_tiktok_auth(tiktok_auth)

        table_tiktok = self._tiny_db.table("tiktok_auth")
        table_tiktok.insert(tiktok_auth.dict())
        return tiktok_auth

    def get_yt_auth(
        self,
        client_id: str,
    ) -> YtAuth | None:
        table_video = self._tiny_db.table("yt_auth")
        if not (results := table_video.search(Query().client_id == client_id)):
            return None

        return YtAuth.parse_obj(results[0])

    def update_yt_auth(
        self,
        yt_auth: YtAuth,
    ) -> YtAuth | None:
        table_yt_auth = self._tiny_db.table("yt_auth")
        table_yt_auth.update(yt_auth.dict(), Query().client_id == yt_auth.client_id)
        return yt_auth

    def add_or_update_yt_auth(
        self,
        yt_auth: YtAuth,
    ) -> YtAuth:
        if self.get_yt_auth(yt_auth.client_id):
            return self.update_yt_auth(yt_auth)

        table_yt_auth = self._tiny_db.table("yt_auth")
        table_yt_auth.insert(yt_auth.dict())
        return yt_auth

    def update_release(
        self,
        release: Release,
    ) -> Release | None:
        table_release = self._tiny_db.table("release")
        table_release.update(release.dict(), Query().release_id == release.release_id)
        return release

    def is_release_at_date(
        self,
        release_platform: ReleasePlatform,
        release_date: date,
    ) -> bool:
        table_release = self._tiny_db.table("release")
        from_datetime = datetime.combine(release_date, datetime.min.time())
        to_datetime = datetime.combine(release_date, datetime.max.time())
        results = table_release.search(
            (Query().release_platform == release_platform.value)
            & (from_datetime.timestamp() < Query().published_at < to_datetime.timestamp())
        )
        return True if results and len(results) > 0 else False

    def get_release(
        self,
        release_id: str,
    ) -> Release | None:
        table_release = self._tiny_db.table("release")
        if not (results := table_release.search(Query().release_id == release_id)):
            return None

        return Release.parse_obj(results[0])

    def add_or_update_release(
        self,
        release: Release,
    ) -> Release:
        table_release = self._tiny_db.table("release")
        if self.get_release(release_id=release.release_id):
            return self.update_release(release)

        table_release.insert(release.dict())
        return release

    def _get_all_points_by_video(
        self,
        video_id: list[str] | int | None = None,
        datetime: datetime | None = None,
    ) -> Iterator[list[Point]]:
        timequery = None
        if datetime:
            from_datetime = datetime.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            until_datetime = from_datetime.replace(hour=23, minute=59, second=59, microsecond=0)
            timequery = (TimeQuery() > from_datetime) & (TimeQuery() < until_datetime)

        if not video_id:
            video_id_list = list(set(self._db.get_tag_values()["video_id"]))
        elif isinstance(video_id, int):
            video_id_list = [video_id]
        else:
            video_id_list = video_id

        video_id_list.sort()

        for video_id in video_id_list:
            query = TagQuery().video_id == video_id
            if timequery:
                query = (query) & (timequery)
            yield self._db.search(
                query=query,
                # sorted=True,
            )

    def get_all_points_by_video(
        self,
        video_id: list[str] | int | None = None,
        datetime: datetime | None = None,
    ) -> Iterator[list[VideoPoint]]:
        for points in self._get_all_points_by_video(video_id=video_id, datetime=datetime):
            if not points:
                continue
            yield [self._map_point_video_point(point) for point in points]

    def get_last_timeseries_datetime(self) -> datetime | None:
        if not (timeseries := list(set(self._db.get_timestamps()))):
            return
        timeseries.sort(reverse=True)
        last_timeseries = timeseries[0]
        return last_timeseries.astimezone(timezone.utc)

    def _map_and_enrich(self, point: Point) -> VideoPoint:
        video_point = self._map_point_video_point(point)
        video_detail = self.get_video(video_id=video_point.video_id)
        video_point.title = video_detail.title
        video_point.description = video_detail.description
        video_point.channel = video_detail.channel
        video_point.duration = video_detail.duration
        return video_point

    def get_last_timeseries_videos(self) -> Iterator[VideoPoint]:
        if not (last_timeseries_datetime := self.get_last_timeseries_datetime()):
            return

        for point in self._db.search(TimeQuery() == last_timeseries_datetime):
            yield self._map_and_enrich(point)

    def get_today_timeseries_videos(self) -> Iterator[VideoPoint]:
        from_datetime = datetime.combine(date.today(), datetime.min.time())
        for point in self._db.search(TimeQuery() > from_datetime):
            yield self._map_and_enrich(point)

    def get_defined_range_timeseries_videos(
        self,
        timeseries_range: TimeseriesRange,
        day: PastDate = None,
    ) -> Iterator[VideoPoint]:
        from_datetime = VideoPointTools.calculate_datetime_for_range(
            timeseries_range=timeseries_range,
            day=day,
        )
        until_datetime = from_datetime + timedelta(days=1)
        timequery = (TimeQuery() > from_datetime) & (TimeQuery() < until_datetime)

        for point in self._db.search(timequery):
            yield self._map_and_enrich(point)

    def get_top_25_videos(
        self,
        timeseries_range: TimeseriesRange = TimeseriesRange.WEEKLY,
        day: PastDate = None,
    ) -> list[Video]:
        previous_video_list: list[VideoPoint] = list(
            self.get_defined_range_timeseries_videos(
                timeseries_range=timeseries_range,
                day=day,
            )
        )

        current_video_list: list[VideoPoint] = list(
            self.get_defined_range_timeseries_videos(
                timeseries_range=TimeseriesRange.DAILY,
                day=day + timedelta(days=1),
            )
        )

        if not current_video_list:
            logger.error("Not video timeseries for today, fetch today first")
            raise IndexError("Not video timeseries for today, fetch today first")

        return [
            Video.parse_obj(video_point.dict())
            for video_point in VideoPointTools.generate_top_list_compared(
                current_video_list=current_video_list, previous_video_list=previous_video_list
            )
        ]

    @staticmethod
    def _map_point_video_point(point: Point) -> VideoPoint:
        return VideoPoint(
            time=point.time,
            video_id=point.tags["video_id"],
            views=point.fields["views"],
            likes=point.fields["likes"],
            views_growth=point.fields["views_growth"] if "views_growth" in point.fields else None,
            score=point.fields["score"] if "score" in point.fields else None,
            score_status=point.tags["score_status"] if "score_status" in point.tags else None,
        )


def video_list_mapper_hashtags(video_list: list[Video] = None) -> list[str]:
    hashtag_list = set()
    if not video_list:
        return []

    for video in video_list:
        hashtag_list.update(video.hashtags_in_description)
    return list(hashtag_list)
