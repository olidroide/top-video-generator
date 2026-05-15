import re
from typing import Final

from src.config.settings import AppSettings
from src.domain.models import CanonicalVideo
from src.infrastructure.youtube.schemas import YTVideo
from src.infrastructure.youtube.yt_client import YTClient

_YT_DURATION_REGEX: Final[re.Pattern[str]] = re.compile(
    r"^P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$"
)


def _parse_yt_duration_seconds(duration: str) -> float:
    """Parse YouTube ISO-8601 duration (e.g. PT4M15S) to seconds."""
    if not duration:
        return 0.0

    if not (match := _YT_DURATION_REGEX.fullmatch(duration)):
        return 0.0

    days = int(match.group("days") or 0)
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)

    total_seconds = (days * 24 * 60 * 60) + (hours * 60 * 60) + (minutes * 60) + seconds
    return float(total_seconds)


class YouTubeSource:
    def __init__(self, client: YTClient | None = None, settings: AppSettings | None = None) -> None:
        self.client = client if client is not None else YTClient(settings=settings)

    async def fetch_trending_videos(
        self,
        *,
        region: str = "",
        date: str | None = None,
        limit: int = 50,
    ) -> list[CanonicalVideo]:
        _ = region, date
        trending_data = await self.client.get_popular_videos(max_results=limit)
        return [self._yt_video_to_canonical(item) for item in trending_data.items]

    async def fetch_video_details_batch(self, video_ids: list[str]) -> list[CanonicalVideo]:
        details = await self.client.get_video_details_batch(video_ids)
        return [self._yt_video_to_canonical(item) for item in details.items]

    def _yt_video_to_canonical(self, item: YTVideo) -> CanonicalVideo:
        snippet = item.snippet
        statistics = item.statistics
        content_details = item.content_details

        title = (snippet.title or "") if snippet else ""
        channel_name = (snippet.channel_title or "") if snippet else ""
        views = int(statistics.view_count or 0) if statistics else 0
        likes = int(statistics.like_count or 0) if statistics else 0

        thumbnail_url: str | None = None
        if snippet and snippet.thumbnails:
            if snippet.thumbnails.high:
                thumbnail_url = snippet.thumbnails.high.url
            elif snippet.thumbnails.medium:
                thumbnail_url = snippet.thumbnails.medium.url
            elif snippet.thumbnails.default:
                thumbnail_url = snippet.thumbnails.default.url

        duration_seconds = 0.0
        if content_details and content_details.duration:
            duration_seconds = _parse_yt_duration_seconds(content_details.duration)

        description = (snippet.description or "") if snippet else ""

        return CanonicalVideo(
            video_id=item.id,
            title=title,
            channel_name=channel_name,
            views=views,
            views_growth=0,
            score=0.0,
            score_previous=0.0,
            thumbnail_url=thumbnail_url,
            description=description,
            duration_seconds=duration_seconds,
            likes=likes,
        )
