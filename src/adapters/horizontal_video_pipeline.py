"""Adapter for horizontal video rendering pipeline."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.application.workers.factory import WorkerFactory
from src.infrastructure.video.asset_manager import VideoAssetManager
from src.infrastructure.video.compositor import VideoCompositor
from src.infrastructure.video.downloader import VideoDownloader
from src.infrastructure.video.renderer import VideoRenderer
from src.infrastructure.video.thumbnail_generator import ThumbnailGenerator

if TYPE_CHECKING:
    from collections.abc import Sequence

    from src.config.settings import AppSettings
    from src.domain.models import Video


class HorizontalVideoPipelineAdapter:
    """Build final horizontal video artifact plus thumbnail from ranked source videos."""

    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings

    async def build_horizontal_video(self, video_list: Sequence[Video]) -> tuple[str, str]:
        downloader = VideoDownloader()
        selected_videos = list(video_list)
        await downloader.download_video(selected_videos)
        WorkerFactory().start_workers(selected_videos)

        asset_manager = VideoAssetManager(
            end_screen_file=self._settings.video_template_end_screen_file or "",
            start_screen_file=self._settings.video_template_start_screen_file or "",
            template_file=self._settings.video_template_file or "",
            template_vertical_file=self._settings.video_template_vertical_file or "",
            thumbnail_file=self._settings.video_template_thumbnail_file or "",
            thumbnail_font_file=self._settings.video_template_thumbnail_font_file or "",
            video_yt_resources_folder=downloader.video_yt_resources_folder,
            video_generated_base_folder=self._settings.video_generated_folder,
        )
        renderer = VideoRenderer(asset_manager)
        compositor = VideoCompositor(asset_manager, renderer)
        thumbnail_generator = ThumbnailGenerator(asset_manager)

        file_path = await compositor.join_processed_videos([video.video_id for video in selected_videos])
        thumbnail_path = await thumbnail_generator.generate_thumbnail(selected_videos[-4:])
        return file_path, thumbnail_path
