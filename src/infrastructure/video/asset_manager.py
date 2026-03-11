"""Video Asset Manager - file paths, folder management, cleanup.

Part of C1 split (video_processing.py -> infrastructure/video/).
Extracted: March 5, 2026 - Phase 4 hexagonal architecture.

This module handles all file system operations for video generation:
- Generated video folder paths (with date stamping)
- Template file path storage
- Cleanup of processed videos
- No MoviePy dependencies (lowest coupling class)
"""

import datetime
import pathlib
import shutil

from src.shared.logging import get_logger

logger = get_logger(__name__)


class VideoAssetManager:
    """Manages file paths, folders, and cleanup for video production.

    Responsibilities:
    - Store template file paths (start/end screens, overlays, fonts)
    - Create dated output folders (YYYYMMDD)
    - Provide cleanup for generated files

    Does NOT:
    - Render video clips (see VideoRenderer)
    - Compose final videos (see VideoCompositor)
    - Generate thumbnails (see ThumbnailGenerator)
    """

    def __init__(
        self,
        *,
        end_screen_file: str,
        start_screen_file: str,
        template_file: str,
        template_vertical_file: str,
        thumbnail_file: str,
        thumbnail_font_file: str,
        video_yt_resources_folder: str,
        video_generated_base_folder: str,
    ) -> None:
        """Initialize asset manager with all required paths.

        Args:
            end_screen_file: Path to end screen video template
            start_screen_file: Path to start screen video template
            template_file: Path to horizontal overlay template
            template_vertical_file: Path to vertical overlay template
            thumbnail_file: Path to thumbnail base image
            thumbnail_font_file: Path to font for thumbnail text
            video_yt_resources_folder: Folder containing downloaded YouTube videos
            video_generated_base_folder: Base folder for generated output videos
        """
        self._end_screen_file = end_screen_file
        self._start_screen_file = start_screen_file
        self._template_file = template_file
        self._template_vertical_file = template_vertical_file
        self._thumbnail_file = thumbnail_file
        self._thumbnail_font_file = thumbnail_font_file
        self._video_yt_resources_folder = video_yt_resources_folder

        # Create dated output folder (e.g., generated/20260305/)
        path = pathlib.Path(f"{video_generated_base_folder}/{datetime.datetime.now(datetime.UTC).strftime('%Y%m%d')}/")
        path.mkdir(parents=True, exist_ok=True)
        self._video_generated_folder = str(path)

    @property
    def end_screen_file(self) -> str:
        """Path to end screen template video."""
        return self._end_screen_file

    @property
    def start_screen_file(self) -> str:
        """Path to start screen template video."""
        return self._start_screen_file

    @property
    def template_file(self) -> str:
        """Path to horizontal overlay template."""
        return self._template_file

    @property
    def template_vertical_file(self) -> str:
        """Path to vertical overlay template."""
        return self._template_vertical_file

    @property
    def thumbnail_file(self) -> str:
        """Path to thumbnail base image."""
        return self._thumbnail_file

    @property
    def thumbnail_font_file(self) -> str:
        """Path to font file for thumbnail rendering."""
        return self._thumbnail_font_file

    @property
    def video_yt_resources_folder(self) -> str:
        """Folder containing downloaded YouTube video files."""
        return self._video_yt_resources_folder

    @property
    def video_generated_folder(self) -> str:
        """Folder for generated output videos (dated: YYYYMMDD)."""
        return self._video_generated_folder

    async def delete_processed_videos(self) -> None:
        """Remove all generated videos from today's dated folder.

        This cleanup method removes the entire dated output folder
        (e.g., generated/20260305/) including all files within it.

        Raises:
            No exceptions raised - logs errors if deletion fails.
        """
        try:
            shutil.rmtree(self._video_generated_folder)
            logger.info("deleted_processed_videos", folder=self._video_generated_folder)
        except Exception as e:
            logger.error(
                "failed_to_delete_processed_videos",
                folder=self._video_generated_folder,
                exception=str(e),
            )
