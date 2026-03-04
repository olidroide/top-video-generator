import asyncio
from typing import Any
from src.yt_client import YTClient
from src.domain.models import CanonicalVideo, VideoScoreStatus
from src.domain.ports import VideoDataSource

class YouTubeSource:
    def __init__(self):
        self.client = YTClient()

    async def fetch_top_videos(self, *, region: str, date: str | None = None, limit: int = 50) -> list[CanonicalVideo]:
        # YTClient is likely blocking, so use to_thread
        trending = await asyncio.to_thread(self.client.get_popular_videos, region=region, limit=limit)
        details = await asyncio.to_thread(self.client.get_video_details_batch, [item["video_id"] for item in trending])
        return [self._to_canonical(item, details.get(item["video_id"])) for item in trending]

    async def fetch_video_details_batch(self, video_ids: list[str]) -> list[CanonicalVideo]:
        details = await asyncio.to_thread(self.client.get_video_details_batch, video_ids)
        return [self._to_canonical(v, details.get(v["video_id"])) for v in details.values()]

    def _to_canonical(self, item: dict[str, Any], details: dict[str, Any] | None = None) -> CanonicalVideo:
        d = details or item
        return CanonicalVideo(
            video_id=d["video_id"],
            title=d["title"],
            channel_name=d["channel_name"],
            views=int(d.get("views", 0)),
            views_growth=0,
            score=0.0,
            score_previous=0.0,
            score_status=VideoScoreStatus.NEW,
            thumbnail_url=d.get("thumbnail_url", ""),
        )

assert isinstance(YouTubeSource(), VideoDataSource)
