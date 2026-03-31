# pyright: reportMissingTypeStubs=false

"""VideoCompositor — Video compositing and rendering (horizontal + vertical formats).

C1.4 extraction: Composes individual video clips with overlays, joins multiple clips
with transitions, and renders final videos.
"""

import asyncio
import datetime
import pathlib
import tempfile
from typing import Any

from src.config.settings import get_app_settings
from src.domain.models import Video
from src.shared.logging import get_logger

from .asset_manager import VideoAssetManager
from .moviepy_compat import (
    CompositeVideoClip,
    VideoFileClip,
    clip_subclipped,
    clip_with_audio_fade_out,
    clip_with_crossfade_in,
    clip_with_position,
    clip_with_start,
    close_clip,
    video_target_resolution,
)
from .renderer import VideoRenderer

logger = get_logger(__name__)

CLIP_TRIM_THRESHOLD_SECONDS = 50


class VideoCompositor:
    """Composes video clips with overlays and renders final videos.

    Handles:
    - post_process_video(): horizontal (1920x1080) format composition
    - post_process_vertical_video(): vertical (1080x1920) format composition
    - join_processed_videos(): joining multiple clips with cross-fade transitions
    - _render_clip(): FFmpeg rendering with h264 codec

    Dependencies:
        - VideoAssetManager: provides paths (start_screen, end_screen, video_generated_folder)
        - VideoRenderer: provides overlay methods (overlay_with_video_template, overlay_texts_template, etc.)
        - moviepy: video clip composition and rendering
        - FFmpeg: via moviepy.write_videofile()
    """

    def __init__(self, asset_manager: VideoAssetManager, renderer: VideoRenderer) -> None:
        """Initialize with VideoAssetManager and VideoRenderer.

        Args:
            asset_manager: VideoAssetManager instance providing resource paths.
            renderer: VideoRenderer instance providing overlay methods.
        """
        self._asset_manager = asset_manager
        self._renderer = renderer
        # Path shims for backward compatibility
        self._start_screen_file = asset_manager.start_screen_file
        self._end_screen_file = asset_manager.end_screen_file
        self._video_yt_resources_folder = asset_manager.video_yt_resources_folder
        self._video_generated_folder = asset_manager.video_generated_folder

    async def post_process_video(self, video: Video) -> None:
        """Compose horizontal video (1920x1080) with overlays and render.

        Args:
            video: Video object with metadata for overlays.
        """
        logger.debug("start post_process_video", video=video.video_id)
        x_width = 1920
        y_height = 1080
        seconds_per_clip = 8
        clip = VideoFileClip(
            filename=f"{self._video_yt_resources_folder}/{video.video_id}.mp4",
            target_resolution=video_target_resolution(x_width, y_height),
        )
        raw_duration: Any = getattr(clip, "duration", 0.0)
        clip_duration = float(raw_duration or 0.0)
        if clip_duration < CLIP_TRIM_THRESHOLD_SECONDS:
            clip = clip_subclipped(clip, 0, seconds_per_clip)
        else:
            start = int(clip_duration / 2)
            clip = clip_subclipped(clip, start, start + seconds_per_clip)

        composite_video_clip: CompositeVideoClip | None = None
        try:
            clips = list(await self._renderer.overlay_with_video_template(video_file_clip=clip))
            clips.extend(self._renderer.overlay_texts_template(video_file_clip=clip, video=video))

            composite_video_clip = CompositeVideoClip(clips=clips)
            await self._render_clip(composite_video_clip, video.video_id)
        finally:
            close_clip(composite_video_clip)
            close_clip(clip)
        logger.debug("finish post_process_video", video=video.video_id)

    async def post_process_vertical_video(self, video: Video) -> None:
        """Compose vertical video (1080x1920) with overlays and render.

        Args:
            video: Video object with metadata for overlays.
        """
        logger.debug("start post_process_vertical_video", video=video.video_id)
        _x_width = 1080
        _y_height = 1920
        seconds_per_clip = 8
        clip = VideoFileClip(
            filename=f"{self._video_yt_resources_folder}/{video.video_id}.mp4",
        )
        clip = clip_with_position(clip, "top")
        clip_duration = float(clip.duration or 0.0)
        if clip_duration < CLIP_TRIM_THRESHOLD_SECONDS:
            clip = clip_subclipped(clip, 0, seconds_per_clip)
        else:
            start = int(clip_duration / 2)
            clip = clip_subclipped(clip, start, start + seconds_per_clip)

        composite_video_clip: CompositeVideoClip | None = None
        try:
            clips = list(await self._renderer.overlay_with_vertical_video_template(video_file_clip=clip))
            clips.extend(self._renderer.overlay_texts_vertical_template(video_file_clip=clip, video=video))

            composite_video_clip = CompositeVideoClip(clips=clips)
            await self._render_clip(composite_video_clip, f"{video.video_id}_vertical")
        finally:
            close_clip(composite_video_clip)
            close_clip(clip)

        logger.debug("finish post_process_vertical_video", video=video.video_id)

    async def join_processed_videos(self, video_id_list: list[str], vertical: bool = False) -> str:
        """Join multiple processed videos with cross-fade transitions.

        Adds start_screen (horizontal only) and end_screen as bookends.

        Args:
            video_id_list: List of video IDs to join.
            vertical: If True, skip start/end screens (vertical-only feature).

        Returns:
            Path to joined video file.
        """
        cross_fade_duration = 1
        if not vertical:
            start_clip: Any = VideoFileClip(self._start_screen_file)
            composite_clips = [
                clip_with_audio_fade_out(start_clip, cross_fade_duration),
            ]
        else:
            video_id = video_id_list.pop(0)
            file_path = f"{self._video_generated_folder}/{video_id}{'_vertical' if vertical else ''}_format.mp4"
            first_vertical_clip: Any = VideoFileClip(file_path)
            composite_clips = [
                clip_with_audio_fade_out(first_vertical_clip, cross_fade_duration),
            ]

        for index, video_id in enumerate(video_id_list):
            clip = VideoFileClip(
                f"{self._video_generated_folder}/{video_id}{'_vertical' if vertical else ''}_format.mp4"
            )
            composite_clips.append(
                clip_with_crossfade_in(
                    clip_with_audio_fade_out(
                        clip_with_start(clip, composite_clips[index].end - cross_fade_duration),
                        cross_fade_duration,
                    ),
                    cross_fade_duration,
                )
            )

        if not vertical:
            clip = VideoFileClip(self._end_screen_file)
            composite_clips.append(
                clip_with_crossfade_in(
                    clip_with_audio_fade_out(
                        clip_with_start(clip, composite_clips[len(composite_clips) - 1].end - cross_fade_duration),
                        cross_fade_duration,
                    ),
                    cross_fade_duration,
                )
            )

        merged_clip: CompositeVideoClip | None = None
        try:
            merged_clip = CompositeVideoClip(clips=composite_clips)
            return await self._render_clip(
                merged_clip,
                datetime.datetime.now(datetime.UTC).strftime("%Y%m%d") + f"{'_vertical' if vertical else ''}",
            )
        finally:
            close_clip(merged_clip)
            for clip in composite_clips:
                close_clip(clip)

    async def _render_clip(self, video: CompositeVideoClip, video_id: str) -> str:
        """Render CompositeVideoClip to MP4 file using FFmpeg.

        Skips rendering if output file already exists (idempotency check).

        Args:
            video: CompositeVideoClip to render.
            video_id: Identifier for output filename ({video_id}_format.mp4).

        Returns:
            Path to rendered MP4 file.
        """
        logger.debug("start render clip", video_id=video_id)
        path = pathlib.Path(f"{self._video_generated_folder}/{video_id}_format.mp4")
        if await asyncio.to_thread(path.exists):
            return str(path)
        if not (threads := get_app_settings().threads_workers):
            threads = 1

        video.write_videofile(
            str(path),
            remove_temp=True,
            temp_audiofile=str(pathlib.Path(tempfile.gettempdir()) / f"temp_{video_id}_audio.mp4"),
            verbose=False,
            logger=None,
            fps=24,
            codec="libx264",
            threads=threads,
            preset="ultrafast",
        )

        return str(path)
