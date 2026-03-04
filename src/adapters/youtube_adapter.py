"""Async adapter for YouTube client using run_in_executor."""

import asyncio
from typing import Any

from googleapiclient.http import MediaFileUpload

from src.logger import get_logger
from src.yt_client import YTClient

logger = get_logger(__name__)


class YouTubeAsyncAdapter:
    """Async wrapper for the synchronous YouTube API client.
    
    Uses asyncio.run_in_executor to prevent blocking the event loop
    when calling googleapiclient methods.
    """
    
    def __init__(self) -> None:
        self._client = YTClient()
    
    async def _run_in_executor(self, func, *args, **kwargs) -> Any:
        """Run a blocking function in the default executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, *args, **kwargs)
    
    async def get_popular_videos(self, max_results: int = 25) -> dict:
        """Fetch popular videos asynchronously."""
        return await self._run_in_executor(
            self._client.get_popular_videos,
            max_results
        )
    
    async def get_video_details(self, video_id: str) -> dict:
        """Fetch video details asynchronously."""
        return await self._run_in_executor(
            self._client._fetch_video_details,
            video_id
        )
    
    async def upload_video(
        self,
        video_path: str,
        title: str,
        description: str,
        tags: list[str],
        category_id: str = "10"
    ) -> dict:
        """Upload a video to YouTube asynchronously.
        
        Args:
            video_path: Path to the video file
            title: Video title
            description: Video description
            tags: List of tags
            category_id: YouTube category ID (default: 10 for Music)
            
        Returns:
            API response dict
        """
        def _upload():
            youtube = self._client.get_authenticated_service()
            body = {
                "snippet": {
                    "title": title,
                    "description": description,
                    "tags": tags,
                    "categoryId": category_id,
                },
                "status": {
                    "privacyStatus": "public",
                    "selfDeclaredMadeForKids": False,
                },
            }
            
            media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
            request = youtube.videos().insert(
                part=",".join(body.keys()),
                body=body,
                media_body=media,
            )
            
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    logger.info(f"📹 Upload progress: {int(status.progress() * 100)}%")
            
            return response
        
        return await self._run_in_executor(_upload)
    
    async def add_video_to_playlist(
        self,
        playlist_id: str,
        video_id: str,
        position: int = 0
    ) -> dict:
        """Add a video to a playlist asynchronously."""
        return await self._run_in_executor(
            self._client._add_playlist_item,
            playlist_id,
            video_id,
            position
        )
    
    async def remove_video_from_playlist(self, playlist_item_id: str) -> dict:
        """Remove a video from a playlist asynchronously."""
        return await self._run_in_executor(
            self._client._delete_playlist_item,
            playlist_item_id
        )
