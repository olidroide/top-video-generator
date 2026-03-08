import datetime
import pathlib
import shutil
from datetime import timezone

import requests
import segno as segno
from millify import millify
from moviepy import Clip
from moviepy.audio.fx.audio_fadeout import audio_fadeout
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from moviepy.video.compositing.transitions import crossfadein
from moviepy.video.fx.crop import crop
from moviepy.video.fx.mask_color import mask_color
from moviepy.video.fx.resize import resize
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.VideoClip import ColorClip, ImageClip, TextClip
from PIL import Image, ImageDraw, ImageFont

from src.db_client import Video, VideoScoreStatus
from src.infrastructure.video.asset_manager import VideoAssetManager
from src.infrastructure.video.compositor import VideoCompositor
from src.infrastructure.video.renderer import VideoRenderer
from src.infrastructure.video.thumbnail_generator import ThumbnailGenerator
from src.logger import get_logger
from src.settings import get_app_settings
from src.video_downloader import VideoDownloader

logger = get_logger(__name__)


class VideoProcessing:
    def __init__(self) -> None:
        super().__init__()
        settings = get_app_settings()
        
        # Delegate asset management to VideoAssetManager (C1.1 migration)
        self._asset_manager = VideoAssetManager(
            end_screen_file=settings.video_template_end_screen_file,
            start_screen_file=settings.video_template_start_screen_file,
            template_file=settings.video_template_file,
            template_vertical_file=settings.video_template_vertical_file,
            thumbnail_file=settings.video_template_thumbnail_file,
            thumbnail_font_file=settings.video_template_thumbnail_font_file,
            video_yt_resources_folder=VideoDownloader().video_yt_resources_folder,
            video_generated_base_folder=settings.video_generated_folder,
        )
        
        # Delegate rendering to VideoRenderer (C1.2 migration)
        self._renderer = VideoRenderer(asset_manager=self._asset_manager)
        
        # Delegate thumbnail generation to ThumbnailGenerator (C1.3 migration)
        self._thumbnail_generator = ThumbnailGenerator(asset_manager=self._asset_manager)
        
        # Delegate video composition to VideoCompositor (C1.4 migration)
        self._compositor = VideoCompositor(asset_manager=self._asset_manager, renderer=self._renderer)
        
        # Backward compatibility shims (delegate to asset_manager)
        self._end_screen_file = self._asset_manager.end_screen_file
        self._start_screen_file = self._asset_manager.start_screen_file
        self._template_file = self._asset_manager.template_file
        self._template_vertical_file = self._asset_manager.template_vertical_file
        self._thumbnail_file = self._asset_manager.thumbnail_file
        self._thumbnail_font_file = self._asset_manager.thumbnail_font_file
        self._video_yt_resources_folder = self._asset_manager.video_yt_resources_folder
        self._video_generated_folder = self._asset_manager.video_generated_folder

    def _overlay_texts_template(self, video_file_clip: VideoFileClip, video: Video) -> list[TextClip]:
        """Generate horizontal text overlays (delegates to VideoRenderer)."""
        return self._renderer.overlay_texts_template(video_file_clip=video_file_clip, video=video)

    def _overlay_texts_vertical_template(self, video_file_clip: VideoFileClip, video: Video) -> list[TextClip]:
        """Generate vertical text overlays (delegates to VideoRenderer)."""
        return self._renderer.overlay_texts_vertical_template(video_file_clip=video_file_clip, video=video)

    async def _overlay_with_video_template(self, video_file_clip: VideoFileClip) -> list[Clip]:
        """Apply horizontal template (delegates to VideoRenderer)."""
        return await self._renderer.overlay_with_video_template(video_file_clip=video_file_clip)

    async def _overlay_with_vertical_video_template(self, video_file_clip: VideoFileClip) -> list[Clip]:
        """Apply vertical template (delegates to VideoRenderer)."""
        return await self._renderer.overlay_with_vertical_video_template(video_file_clip=video_file_clip)

    async def post_process_video(self, video: Video) -> None:
        """Compose horizontal video with overlays (delegates to VideoCompositor)."""
        return await self._compositor.post_process_video(video=video)

    async def post_process_vertical_video(self, video: Video) -> None:
        """Compose vertical video with overlays (delegates to VideoCompositor)."""
        return await self._compositor.post_process_vertical_video(video=video)

    async def join_processed_videos(self, video_id_list: list[str], vertical: bool = False) -> str:
        """Join multiple processed videos (delegates to VideoCompositor)."""
        return await self._compositor.join_processed_videos(video_id_list=video_id_list, vertical=vertical)

    async def generate_thumbnail(self, video_list: list[Video]) -> str:
        """Generate 2x2 grid thumbnail (delegates to ThumbnailGenerator)."""
        return await self._thumbnail_generator.generate_thumbnail(video_list=video_list)

    async def _render_clip(self, video: CompositeVideoClip, video_id: str) -> str:
        logger.debug("start render clip", video_id=video_id)
        path = pathlib.Path(f"{self._video_generated_folder}/{video_id}_format.mp4")
        if path.exists():
            return str(path)
        if not (threads := get_app_settings().threads_workers):
            threads = 1

        video.write_videofile(
            str(path),
            remove_temp=True,
            temp_audiofile=f"/tmp/temp_{video_id}_audio.mp4",
            verbose=False,
            logger=None,
            fps=24,
            codec="libx264",  # or use newer "libx265"
            # codec="libx265",  # better compression
            threads=threads,
            preset="ultrafast",  # veryfast
            # bitrate="8M",
        )

        return str(path)

    async def delete_processed_videos(self):
        """Remove all generated videos (delegates to VideoAssetManager)."""
        await self._asset_manager.delete_processed_videos()
