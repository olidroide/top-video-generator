import isodate

from src.domain.models import CanonicalVideo
from src.infrastructure.youtube import YTClient
from src.infrastructure.youtube.schemas import YTVideo


class YouTubeSource:
    def __init__(self) -> None:
        self.client = YTClient()

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
        content_details = item.contentDetails

        title = (snippet.title or "") if snippet else ""
        channel_name = (snippet.channelTitle or "") if snippet else ""
        views = int(statistics.viewCount or 0) if statistics else 0
        likes = int(statistics.likeCount or 0) if statistics else 0

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
            try:
                duration_seconds = float(isodate.parse_duration(content_details.duration).total_seconds())
            except (ValueError, AttributeError):
                duration_seconds = 0.0

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
