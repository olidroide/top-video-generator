"""YouTube Data API request helpers."""

import asyncio
from collections.abc import Callable

from googleapiclient.errors import HttpError

from src.shared.logging import get_logger

logger = get_logger(__name__)


class YouTubeApiClient:
    """Encapsulates YouTube Data API calls used by the pipeline."""

    def __init__(
        self,
        *,
        get_authenticated_service: Callable,
        search_language_code: str,
        search_region_code: str,
        search_category_code: str,
    ) -> None:
        self._get_authenticated_service = get_authenticated_service
        self._search_language_code = search_language_code
        self._search_region_code = search_region_code
        self._search_category_code = search_category_code

    async def fetch_popular_videos(self, max_results: int = 25) -> dict:
        try:
            youtube = self._get_authenticated_service()
            return await asyncio.to_thread(
                lambda: (
                    youtube.videos()
                    .list(
                        part="contentDetails",
                        chart="mostPopular",
                        hl=self._search_language_code,
                        maxResults=max_results,
                        regionCode=self._search_region_code,
                        videoCategoryId=self._search_category_code,
                    )
                    .execute()
                )
            )
        except HttpError as exc:
            logger.exception("youtube_api.fetch_popular_videos_failed", error=str(exc))
            return {}

    async def get_uploads_playlist(self) -> str | None:
        try:
            youtube = self._get_authenticated_service()
            response = await asyncio.to_thread(
                lambda: youtube.channels().list(part="contentDetails", mine=True).execute()
            )
            return response.get("items", []).pop().get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
        except HttpError as exc:
            logger.exception("youtube_api.get_uploads_playlist_failed", error=str(exc))
            return None

    async def fetch_videos_of_playlist(self, playlist_id: str, max_results: int = 25) -> dict:
        try:
            youtube = self._get_authenticated_service()
            return await asyncio.to_thread(
                lambda: (
                    youtube.playlistItems()
                    .list(
                        part="contentDetails",
                        playlistId=playlist_id,
                        maxResults=max_results,
                    )
                    .execute()
                )
            )
        except HttpError as exc:
            logger.exception("youtube_api.fetch_videos_of_playlist_failed", error=str(exc))
            return {}

    async def fetch_video_details(self, video_id: str) -> dict:
        try:
            youtube = self._get_authenticated_service()
            return await asyncio.to_thread(
                lambda: (
                    youtube.videos()
                    .list(
                        part="snippet,contentDetails,statistics",
                        id=video_id,
                    )
                    .execute()
                )
            )
        except HttpError as exc:
            logger.exception("youtube_api.fetch_video_details_failed", error=str(exc))
            return {}

    async def fetch_video_details_batch(self, video_ids: list[str]) -> dict:
        try:
            youtube = self._get_authenticated_service()
            ids_param = ",".join(video_ids)
            return await asyncio.to_thread(
                lambda: (
                    youtube.videos()
                    .list(
                        part="snippet,contentDetails,statistics",
                        id=ids_param,
                    )
                    .execute()
                )
            )
        except HttpError as exc:
            logger.exception("youtube_api.fetch_video_details_batch_failed", error=str(exc))
            return {}

    async def fetch_playlist_items(self, playlist_id: str) -> dict:
        try:
            youtube = self._get_authenticated_service()
            return await asyncio.to_thread(
                lambda: (
                    youtube.playlistItems()
                    .list(
                        part="snippet",
                        playlistId=playlist_id,
                        maxResults=50,
                    )
                    .execute()
                )
            )
        except HttpError as exc:
            logger.exception("youtube_api.fetch_playlist_items_failed", error=str(exc))
            return {}

    async def delete_playlist_item(self, playlist_item_id: str) -> dict:
        try:
            youtube = self._get_authenticated_service()
            return await asyncio.to_thread(lambda: youtube.playlistItems().delete(id=playlist_item_id).execute())
        except HttpError as exc:
            logger.exception("youtube_api.delete_playlist_item_failed", error=str(exc))
            return {}

    async def add_playlist_item(self, playlist_id: str, video_id: str, position: int) -> dict:
        try:
            youtube = self._get_authenticated_service()
            return await asyncio.to_thread(
                lambda: (
                    youtube.playlistItems()
                    .insert(
                        part="snippet",
                        body={
                            "snippet": {
                                "playlistId": playlist_id,
                                "resourceId": {
                                    "kind": "youtube#video",
                                    "videoId": video_id,
                                },
                                "position": position,
                            }
                        },
                    )
                    .execute()
                )
            )
        except HttpError as exc:
            logger.exception("youtube_api.add_playlist_item_failed", error=str(exc))
            return {}


__all__ = ["YouTubeApiClient"]
