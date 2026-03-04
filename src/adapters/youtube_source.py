
import asyncio
from typing import Any
from src.yt_client import YTClient
from src.domain.models import CanonicalVideo, VideoScoreStatus
from src.domain.ports import VideoDataSource
import isodate

class YouTubeSource:
    def __init__(self):
        self.client = YTClient()

    async def fetch_top_videos(self, *, region: str = '', date: str | None = None, limit: int = 50) -> list[CanonicalVideo]:
        # region se ignora, solo se usa max_results
        trending_data = await self.client.get_popular_videos(max_results=limit)
        # trending_data puede ser un modelo pydantic o dict
        items = getattr(trending_data, "items", None)
        if items is None:
            items = trending_data
        if items and isinstance(items[0], CanonicalVideo):
            return items
        return [self._to_canonical(item) for item in items]

    async def fetch_video_details_batch(self, video_ids: list[str]) -> list[CanonicalVideo]:
        details = await self.client.get_video_details_batch(video_ids)
        # details puede ser un modelo pydantic o dict
        if hasattr(details, "items"):
            detail_items = details.items
        elif isinstance(details, dict):
            detail_items = details.values()
        else:
            detail_items = details
        result = []
        for v in detail_items:
            # v debe tener estructura de la API de YouTube
            snippet = v.get("snippet", {})
            statistics = v.get("statistics", {})
            content_details = v.get("contentDetails", {})
            # duration_seconds
            duration_str = content_details.get("duration", "")
            try:
                duration_seconds = float(isodate.parse_duration(duration_str).total_seconds()) if duration_str else 0.0
            except Exception:
                duration_seconds = 0.0
            # description
            description = snippet.get("description") or ""
            # likes
            likes = int(statistics.get("likeCount", 0) or 0)
            # title
            title = snippet.get("title") or ""
            # channel_name
            channel_name = snippet.get("channelTitle") or ""
            # video_id
            video_id = v.get("id") or v.get("video_id") or ""
            # thumbnail_url
            thumbnails = snippet.get("thumbnails", {})
            thumbnail_url = ""
            if "high" in thumbnails:
                thumbnail_url = thumbnails["high"].get("url", "")
            elif "default" in thumbnails:
                thumbnail_url = thumbnails["default"].get("url", "")
            # views
            views = int(statistics.get("viewCount", 0) or 0)
            result.append(CanonicalVideo(
                video_id=video_id,
                title=title,
                channel_name=channel_name,
                views=views,
                views_growth=0,
                score=0.0,
                score_previous=0.0,
                score_status=VideoScoreStatus.NEW,
                thumbnail_url=thumbnail_url,
                description=description,
                duration_seconds=duration_seconds,
                likes=likes,
            ))
        return result

    def _to_canonical(self, item: dict[str, Any], details: dict[str, Any] | None = None) -> CanonicalVideo:
        # Para compatibilidad, solo mapea los campos básicos (usado en fetch_top_videos)
        d = details or item
        return CanonicalVideo(
            video_id=d.get("video_id") or d.get("id") or "",
            title=d.get("title") or "",
            channel_name=d.get("channel_name") or "",
            views=int(d.get("views", 0)),
            views_growth=0,
            score=0.0,
            score_previous=0.0,
            score_status=VideoScoreStatus.NEW,
            thumbnail_url=d.get("thumbnail_url", ""),
        )

assert isinstance(YouTubeSource(), VideoDataSource)
