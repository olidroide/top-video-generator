from typing import Any

from src.domain.models import CanonicalVideo
from src.domain.ports import VideoDataSource
from src.infrastructure.youtube.client import YTClient


class YouTubeSource:
    def __init__(self):
        self.client = YTClient()

    async def fetch_trending_videos(
        self, *, region: str = "", date: str | None = None, limit: int = 50
    ) -> list[CanonicalVideo]:
        # region se ignora, solo se usa max_results
        trending_data = await self.client.get_popular_videos(max_results=limit)
        items = getattr(trending_data, "items", None)
        if items is None:
            items = trending_data
        # Convierte a lista si es necesario
        if not isinstance(items, list):
            items = list(items)
        # Si ya son CanonicalVideo y no son tuplas, retorna como lista de CanonicalVideo
        if items and isinstance(items[0], CanonicalVideo) and not isinstance(items[0], tuple):
            return [i for i in items if isinstance(i, CanonicalVideo)]
        # Si son tuplas (key, value), quedarse solo con value
        if items and isinstance(items[0], tuple) and len(items[0]) == 2:
            items = [v for k, v in items]
        # Solo pasar dicts a _to_canonical
        dict_items = [item for item in items if isinstance(item, dict)]
        return [self._to_canonical(item) for item in dict_items]

    async def fetch_video_details_batch(self, video_ids: list[str]) -> list[CanonicalVideo]:
        details = await self.client.get_video_details_batch(video_ids)
        if hasattr(details, "items"):
            detail_items = details.items
        else:
            detail_items = details
        # Convierte a lista si es necesario
        if not isinstance(detail_items, list):
            detail_items = list(detail_items)
        # Si son tuplas (key, value), quedarse solo con value
        if detail_items and isinstance(detail_items[0], tuple) and len(detail_items[0]) == 2:
            detail_items = [v for k, v in detail_items]
        # Solo procesar objetos con los atributos requeridos y que no sean tuplas
        result = []
        for v in detail_items:
            if isinstance(v, tuple):
                continue
            if not (hasattr(v, "snippet") and hasattr(v, "statistics") and hasattr(v, "contentDetails")):
                continue
            snippet = v.snippet
            statistics = v.statistics
            content_details = v.contentDetails
            if not (snippet and statistics and content_details):
                continue
            duration_str = getattr(content_details, "duration", "")
            try:
                import isodate

                duration_seconds = (
                    float(isodate.parse_duration(duration_str).total_seconds()) if duration_str else 0.0
                )
            except Exception:
                duration_seconds = 0.0
            description = getattr(snippet, "description", "") or ""
            likes = int(getattr(statistics, "likeCount", 0) or 0)
            title = getattr(snippet, "title", "") or ""
            channel_name = getattr(snippet, "channelTitle", "") or ""
            video_id = getattr(v, "id", None) or getattr(v, "video_id", "") or ""
            thumbnails = getattr(snippet, "thumbnails", None) or {}
            thumbnail_url = ""
            if "high" in thumbnails:
                thumbnail_url = thumbnails["high"].get("url", "")
            elif "default" in thumbnails:
                thumbnail_url = thumbnails["default"].get("url", "")
            views = int(getattr(statistics, "viewCount", 0) or 0)
            result.append(
                CanonicalVideo(
                    video_id=video_id,
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
            )
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
            thumbnail_url=d.get("thumbnail_url", None),
        )


assert isinstance(YouTubeSource(), VideoDataSource)
