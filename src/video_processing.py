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

    async def post_process_video(self, video: Video):
        logger.debug("start post_process_video", video=video.video_id)
        x_width = 1920
        y_height = 1080
        seconds_per_clip = 8
        clip = VideoFileClip(
            filename=f"{self._video_yt_resources_folder}/{video.video_id}.mp4",
            target_resolution=(y_height, x_width),
        )
        if clip.duration < 50:
            clip = clip.subclip(t_start=0, t_end=seconds_per_clip)
        else:
            start = int(clip.duration / 2)
            clip = clip.subclip(t_start=start, t_end=start + seconds_per_clip)

        clips = list(await self._overlay_with_video_template(video_file_clip=clip))
        clips.extend(self._overlay_texts_template(video_file_clip=clip, video=video))

        composite_video_clip = CompositeVideoClip(clips=clips)

        await self._render_clip(composite_video_clip, video.video_id)
        logger.debug("finish post_process_video", video=video.video_id)

    async def post_process_vertical_video(self, video: Video):
        logger.debug(f"start {self.post_process_vertical_video.__name__}", video=video.video_id)
        _x_width = 1080
        _y_height = 1920
        seconds_per_clip = 8
        clip = VideoFileClip(
            filename=f"{self._video_yt_resources_folder}/{video.video_id}.mp4",
            # target_resolution=(y_height, x_width),
        )
        clip = clip.set_position("top")
        if clip.duration < 50:
            clip = clip.subclip(t_start=0, t_end=seconds_per_clip)
        else:
            start = int(clip.duration / 2)
            clip = clip.subclip(t_start=start, t_end=start + seconds_per_clip)

        clips = list(await self._overlay_with_vertical_video_template(video_file_clip=clip))
        clips.extend(self._overlay_texts_vertical_template(video_file_clip=clip, video=video))

        composite_video_clip = CompositeVideoClip(clips=clips)

        await self._render_clip(composite_video_clip, f"{video.video_id}_vertical")

        logger.debug("finish post_process_vertical_video", video=video.video_id)

    async def join_processed_videos(self, video_id_list: list[str], vertical: bool = False) -> str:
        cross_fade_duration = 1
        if not vertical:
            composite_clips = [
                VideoFileClip(self._start_screen_file).fx(audio_fadeout, cross_fade_duration),
            ]
        else:
            video_id = video_id_list.pop(0)
            file_path = f"{self._video_generated_folder}/{video_id}{'_vertical' if vertical else ''}_format.mp4"
            composite_clips = [
                VideoFileClip(file_path).fx(audio_fadeout, cross_fade_duration),
            ]

        for index, video_id in enumerate(video_id_list):
            clip = VideoFileClip(
                f"{self._video_generated_folder}/{video_id}{'_vertical' if vertical else ''}_format.mp4"
            )
            composite_clips.append(
                crossfadein(
                    clip.set_start(composite_clips[index].end - cross_fade_duration).fx(
                        audio_fadeout, cross_fade_duration
                    ),
                    cross_fade_duration,
                )
            )

        if not vertical:
            clip = VideoFileClip(self._end_screen_file)
            composite_clips.append(
                crossfadein(
                    clip.set_start(composite_clips[len(composite_clips) - 1].end - cross_fade_duration).fx(
                        audio_fadeout, cross_fade_duration
                    ),
                    cross_fade_duration,
                )
            )

        merged_clip = CompositeVideoClip(clips=composite_clips)
        return await self._render_clip(
            merged_clip, datetime.datetime.now(timezone.utc).strftime("%Y%m%d") + f"{'_vertical' if vertical else ''}"
        )

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
