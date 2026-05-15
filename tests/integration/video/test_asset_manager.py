"""Integration tests for VideoAssetManager after C1 extraction."""

import pathlib
import shutil
from datetime import UTC, datetime
from pathlib import Path

from src.infrastructure.video.asset_manager import VideoAssetManager


class TestVideoAssetManagerAfterMigration:
    """Test VideoAssetManager operates correctly after extraction from VideoProcessing."""

    def test_init_creates_dated_folder(self, tmp_path: Path) -> None:
        """Verify __init__ creates video_generated_folder with today's date."""
        manager = VideoAssetManager(
            end_screen_file="src/resources/end.mp4",
            start_screen_file="src/resources/start.mp4",
            template_file="src/resources/template.mp4",
            template_vertical_file="src/resources/template_vertical.mp4",
            thumbnail_file="src/resources/thumb.png",
            thumbnail_font_file="src/resources/font.ttf",
            video_yt_resources_folder=str(tmp_path / "yt"),
            video_generated_base_folder=str(tmp_path / "generated"),
        )

        # Check dated folder created
        today_str = datetime.now(UTC).strftime("%Y%m%d")
        expected_folder = tmp_path / "generated" / today_str
        assert expected_folder.exists()
        assert pathlib.Path(manager.video_generated_folder) == expected_folder

    def test_properties_return_stored_paths(self, tmp_path: Path) -> None:
        """Verify all properties return the paths passed to __init__."""
        manager = VideoAssetManager(
            end_screen_file="test_end.mp4",
            start_screen_file="test_start.mp4",
            template_file="test_template.mp4",
            template_vertical_file="test_vert.mp4",
            thumbnail_file="test_thumb.png",
            thumbnail_font_file="test_font.ttf",
            video_yt_resources_folder=str(tmp_path / "yt"),
            video_generated_base_folder=str(tmp_path / "gen"),
        )

        assert manager.end_screen_file == "test_end.mp4"
        assert manager.start_screen_file == "test_start.mp4"
        assert manager.template_file == "test_template.mp4"
        assert manager.template_vertical_file == "test_vert.mp4"
        assert manager.thumbnail_file == "test_thumb.png"
        assert manager.thumbnail_font_file == "test_font.ttf"
        assert manager.video_yt_resources_folder == str(tmp_path / "yt")

    async def test_delete_processed_videos_removes_folder(self, tmp_path: Path) -> None:
        """Verify delete_processed_videos removes the generated folder."""
        manager = VideoAssetManager(
            end_screen_file="src/resources/end.mp4",
            start_screen_file="src/resources/start.mp4",
            template_file="src/resources/template.mp4",
            template_vertical_file="src/resources/template_vertical.mp4",
            thumbnail_file="src/resources/thumb.png",
            thumbnail_font_file="src/resources/font.ttf",
            video_yt_resources_folder=str(tmp_path / "yt"),
            video_generated_base_folder=str(tmp_path / "generated"),
        )

        folder = pathlib.Path(manager.video_generated_folder)
        assert folder.exists()

        # Create test files inside
        (folder / "video1.mp4").touch()
        (folder / "video2.mp4").touch()

        await manager.delete_processed_videos()

        # Folder should be completely removed
        assert not folder.exists()

    async def test_delete_processed_videos_handles_errors_gracefully(self, tmp_path: Path) -> None:
        """Verify delete_processed_videos doesn't raise if folder already deleted."""
        manager = VideoAssetManager(
            end_screen_file="src/resources/end.mp4",
            start_screen_file="src/resources/start.mp4",
            template_file="src/resources/template.mp4",
            template_vertical_file="src/resources/template_vertical.mp4",
            thumbnail_file="src/resources/thumb.png",
            thumbnail_font_file="src/resources/font.ttf",
            video_yt_resources_folder=str(tmp_path / "yt"),
            video_generated_base_folder=str(tmp_path / "generated"),
        )

        folder = pathlib.Path(manager.video_generated_folder)
        # Manually delete folder
        shutil.rmtree(folder)
        assert not folder.exists()

        # Should not raise
        await manager.delete_processed_videos()
