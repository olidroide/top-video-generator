"""YouTube API client implementation."""

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from src.config.settings import get_app_settings
from src.domain.models import YtAuth
from src.infrastructure.storage.auth_repository import AuthenticationRepository
from src.infrastructure.youtube.auth_manager import MemoryCache, YouTubeAuthManager
from src.infrastructure.youtube.schemas import (
    YTRoot,
    YTVideo,
)
from src.shared.logging import get_logger

logger = get_logger(__name__)


class YTClient:
    YT_API_SERVICE_NAME = "youtube"
    YT_API_VERSION = "v3"

    def __init__(self) -> None:
        super().__init__()
        settings = get_app_settings()
        self._yt_client_secret_file_name: str = settings.yt_client_secret_file or ""
        self._yt_redirect_uri: str = settings.yt_redirect_uri or ""
        self._yt_search_region_code: str = settings.yt_search_region_code
        self._yt_search_language_code: str = settings.yt_search_language_code or ""
        self._yt_search_category_code: str = settings.yt_search_category_code or ""
        self._yt_auth_user_id: str = settings.yt_auth_user_id or ""
        tags_raw = settings.yt_tags or ""
        self._yt_tags: list[str] = [str(tag) for tag in tags_raw.split(",") if tag]
        self._memory_cache = MemoryCache()
        self._authenticated_service: Any | None = None

        self._auth_manager: YouTubeAuthManager = YouTubeAuthManager(
            client_secret_file=self._yt_client_secret_file_name,
            redirect_uri=self._yt_redirect_uri,
            service_name=self.YT_API_SERVICE_NAME,
            service_version=self.YT_API_VERSION,
            cache=self._memory_cache,
        )

    def get_authenticated_service(self) -> Any:
        auth_repo = AuthenticationRepository(Path(get_app_settings().db_data_file))
        yt_auth = auth_repo.get_yt_auth(self._yt_auth_user_id)
        if yt_auth is None:
            raise ValueError("Missing YouTube auth credentials")
        if not self._authenticated_service:
            self._authenticated_service = self._auth_manager.build_authenticated_service(
                credentials_payload=yt_auth.model_dump(),
            )
        return self._authenticated_service

    async def step_1_get_authentication_url(self) -> str:
        return self._auth_manager.get_authentication_url()

    async def step_2_exchange_code_authentication(self, authorization_value: str) -> YtAuth:
        return await asyncio.to_thread(self._auth_manager.exchange_code_authentication, authorization_value)

    async def _fetch_popular_videos(self, max_results: int = 25) -> dict[str, object]:
        try:
            youtube = self.get_authenticated_service()
            return await asyncio.to_thread(
                lambda: (
                    youtube.videos()
                    .list(
                        part="contentDetails",
                        chart="mostPopular",
                        hl=self._yt_search_language_code,
                        maxResults=max_results,
                        regionCode=self._yt_search_region_code,
                        videoCategoryId=self._yt_search_category_code,
                    )
                    .execute()
                )
            )
        except HttpError as exc:
            logger.exception("youtube_api.fetch_popular_videos_failed", error=str(exc))
            return {}

    async def _get_uploads_playlist(self) -> str | None:
        try:
            youtube = self.get_authenticated_service()
            response = await asyncio.to_thread(
                lambda: youtube.channels().list(part="contentDetails", mine=True).execute()
            )
            return response.get("items", []).pop().get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
        except HttpError as exc:
            logger.exception("youtube_api.get_uploads_playlist_failed", error=str(exc))
            return None

    async def _fetch_videos_of_playlist(self, playlist_id: str, max_results: int = 25) -> dict[str, object]:
        try:
            youtube = self.get_authenticated_service()
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

    async def _fetch_video_details(self, video_id: str) -> dict[str, object]:
        try:
            youtube = self.get_authenticated_service()
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

    async def _fetch_video_details_batch(self, video_ids: list[str]) -> dict[str, object]:
        """Internal helper that requests details for multiple videos at once.

        The YouTube API accepts a comma-separated ``id`` parameter, so we
        join the list before making the call.  The discovery client is
        blocking, therefore we delegate the ``execute`` call to
        :pyfunc:`asyncio.to_thread` so the event loop is not blocked.
        """
        try:
            youtube = self.get_authenticated_service()
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

    async def _fetch_playlist_items(self, playlist_id: str) -> dict[str, object]:
        try:
            youtube = self.get_authenticated_service()
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

    async def _delete_playlist_item(
        self,
        playlist_item_id: str,
    ) -> dict[str, object]:
        try:
            youtube = self.get_authenticated_service()
            return await asyncio.to_thread(lambda: youtube.playlistItems().delete(id=playlist_item_id).execute())
        except HttpError as exc:
            logger.exception("youtube_api.delete_playlist_item_failed", error=str(exc))
            return {}

    async def _add_playlist_item(
        self,
        playlist_id: str,
        video_id: str,
        position: int,
    ) -> dict[str, object]:
        try:
            youtube = self.get_authenticated_service()
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

    async def get_popular_videos(
        self,
        max_results: int = 25,
    ) -> YTRoot:
        return YTRoot.model_validate(await self._fetch_popular_videos(max_results=max_results))

    async def get_videos_published(self) -> YTRoot:
        playlist_id = await self._get_uploads_playlist()
        if not playlist_id:
            return YTRoot.model_validate({"kind": "youtube#playlistItemListResponse", "etag": "", "items": []})
        return YTRoot.model_validate(await self._fetch_videos_of_playlist(playlist_id=playlist_id))

    async def check_connection(self) -> str | None:
        return await self._get_uploads_playlist()

    async def get_video_details(self, video_id: str) -> YTRoot:
        return YTRoot.model_validate(await self._fetch_video_details(video_id=video_id))

    async def get_video_details_batch(self, video_ids: list[str]) -> YTRoot:
        """Public wrapper around ``_fetch_video_details_batch``.

        The returned object is validated to ``YTRoot`` just like the
        single-id helper so callers can treat the result uniformly.
        """
        return YTRoot.model_validate(await self._fetch_video_details_batch(video_ids=video_ids))

    async def get_playlist_details(self, playlist_id: str) -> YTRoot:
        return YTRoot.model_validate(await self._fetch_playlist_items(playlist_id=playlist_id))

    async def delete_playlist_item(self, playlist_item_id: str) -> None:
        await self._delete_playlist_item(playlist_item_id=playlist_item_id)

    async def add_playlist_item(
        self,
        playlist_id: str,
        video_id: str,
        position: int,
    ) -> YTVideo:
        return YTVideo.model_validate(
            await self._add_playlist_item(
                playlist_id=playlist_id,
                video_id=video_id,
                position=position,
            )
        )

    async def update_link_original_playlist(
        self,
        playlist_id: str | None = None,
        yt_video_id_list: list[str] | None = None,
    ) -> bool | None:
        if not playlist_id:
            logger.warning("cannot update link original playlist without playlist_id param")
            return None

        if not yt_video_id_list:
            logger.warning("cannot update link original playlist without yt video id list param")
            return None

        playlist_details = await self.get_playlist_details(playlist_id=playlist_id)
        for playlist_item in playlist_details.items:
            try:
                await self.delete_playlist_item(playlist_item_id=playlist_item.id)
            except HttpError:
                logger.exception("fail to remove", playlist_item_id=playlist_item.id)

        for index, yt_video_id in enumerate(yt_video_id_list):
            try:
                await self.add_playlist_item(
                    playlist_id=playlist_id,
                    video_id=yt_video_id,
                    position=index,
                )
            except HttpError:
                logger.exception(
                    "fail to add playlist item",
                    playlist_id=playlist_id,
                    video_id=yt_video_id,
                    position=index,
                )

        return True

    async def upload_video(
        self,
        video_path: str,
        title: str,
        description: str,
        thumbnail_path: str | None = None,
        playlist_id: str | None = None,
        tags: list[str] | None = None,
    ) -> str | None:
        yt_tags = [tag.replace("@@YEAR@@", str(datetime.now(UTC).year)) for tag in self._yt_tags]
        yt_tags.extend([tag.replace("#", "") for tag in tags] if tags else [])
        max_tags = 30

        def _do_upload() -> str | None:
            youtube = self.get_authenticated_service()
            media = MediaFileUpload(video_path, chunksize=-1, resumable=True)

            title_formatted = title[:95]
            description_formatted = description[:4900]

            video = (
                youtube.videos()
                .insert(
                    autoLevels=True,
                    notifySubscribers=True,
                    stabilize=False,
                    part="snippet,status",
                    body={
                        "snippet": {
                            "title": title_formatted,
                            "description": description_formatted,
                            "categoryId": self._yt_search_category_code,
                            "defaultAudioLanguage": self._yt_search_language_code,
                            "tags": yt_tags[:max_tags],
                        },
                        "status": {
                            "privacyStatus": "public",
                        },
                    },
                    media_body=media,
                )
                .execute()
            )

            video_id_local = video.get("id")
            if thumbnail_path and video_id_local:
                youtube.thumbnails().set(videoId=video_id_local, media_body=MediaFileUpload(thumbnail_path)).execute()

            if playlist_id and video_id_local:
                youtube.playlistItems().insert(
                    part="snippet",
                    body={
                        "snippet": {
                            "playlistId": playlist_id,
                            "resourceId": {
                                "kind": "youtube#video",
                                "videoId": video_id_local,
                            },
                        }
                    },
                ).execute()

            return video_id_local

        try:
            return await asyncio.to_thread(_do_upload)
        except HttpError as exc:
            logger.exception("youtube_api.upload_failed", error=str(exc))
            return None


__all__ = ["YTClient"]
