"""Adapter for weekly horizontal YouTube upload."""

from __future__ import annotations

from src.config.settings import get_app_settings
from src.domain.ports import WeeklyYouTubeUploader
from src.infrastructure.youtube.yt_client import YTClient
from src.infrastructure.youtube.yt_fake_client import YTClientFake


def _build_yt_client() -> YTClient:
    settings = get_app_settings()
    return YTClient() if settings.is_production_env else YTClientFake()


class YouTubeWeeklyUploaderAdapter(WeeklyYouTubeUploader):
    async def upload_weekly_video(
        self,
        *,
        video_path: str,
        title: str,
        description: str,
        thumbnail_path: str,
        playlist_id: str | None,
        tags: list[str],
    ) -> str | None:
        return await _build_yt_client().upload_video(
            video_path=video_path,
            title=title,
            description=description,
            thumbnail_path=thumbnail_path,
            playlist_id=playlist_id,
            tags=tags,
        )
