"""YouTube upload helpers."""

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from src.shared.logging import get_logger

logger = get_logger(__name__)


class YouTubeUploader:
    """Encapsulates upload workflow (video, thumbnail, playlist insert)."""

    def __init__(
        self,
        *,
        get_authenticated_service: Callable,
        search_category_code: str,
        search_language_code: str,
        default_tags: list[str],
    ) -> None:
        self._get_authenticated_service = get_authenticated_service
        self._search_category_code = search_category_code
        self._search_language_code = search_language_code
        self._default_tags = default_tags

    async def upload_video(
        self,
        video_path,
        title,
        description,
        thumbnail_path: str | None = None,
        playlist_id: str | None = None,
        tags: list[str] | None = None,
    ) -> str | None:
        yt_tags = [tag.replace("@@YEAR@@", str(datetime.now(UTC).year)) for tag in self._default_tags]
        yt_tags.extend([tag.replace("#", "") for tag in tags] if tags else [])
        max_tags = 30

        def _do_upload():
            youtube = self._get_authenticated_service()
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
                            "categoryId": self._search_category_code,
                            "defaultAudioLanguage": self._search_language_code,
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
            logger.error("An error occurred", error=exc)
            return None


__all__ = ["YouTubeUploader"]
