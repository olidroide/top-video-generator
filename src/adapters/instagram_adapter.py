"""Async adapter for Instagram client using run_in_executor."""

import asyncio

from src.instagram_client import InstagramClient
from src.logger import get_logger

logger = get_logger(__name__)


class InstagramAsyncAdapter:
    """Async wrapper for the synchronous Instagram client.
    
    Uses asyncio.run_in_executor to prevent blocking the event loop
    when calling instagrapi methods.
    """
    
    def __init__(self) -> None:
        self._client = InstagramClient()
    
    async def upload_video(self, video_path: str, caption: str) -> str | None:
        """Upload a video to Instagram asynchronously.
        
        Args:
            video_path: Path to the video file
            caption: Caption for the video
            
        Returns:
            Media ID if successful, None otherwise
        """
        loop = asyncio.get_event_loop()
        try:
            logger.info(f"📸 [AsyncAdapter] Uploading Reel: {video_path}")
            # Run the blocking upload in a thread pool
            result = await loop.run_in_executor(
                None,  # Uses default executor
                self._sync_upload,
                video_path,
                caption
            )
            return result
        except Exception as e:
            logger.error(f"📸 [AsyncAdapter] Upload failed: {e}", exc_info=True)
            return None
    
    def _sync_upload(self, video_path: str, caption: str) -> str | None:
        """Synchronous wrapper for the upload operation."""
        # This runs in a separate thread
        import asyncio
        # Create a new event loop for this thread if needed
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Call the async method synchronously
        return loop.run_until_complete(
            self._client.upload_video(video_path, caption)
        )
