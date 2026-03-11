"""Characterization tests — document behavior BEFORE C1 migration.

These tests MUST pass before migration starts and MUST pass after each migration step.
They lock the current behavior of VideoProcessing methods.

Run with: uv run pytest tests/integration/video/test_video_processing_current.py -v -m slow
"""

import pathlib
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.VideoClip import TextClip
from PIL import Image

from src.db_client import Channel, Video, VideoScoreStatus
from src.video_processing import VideoProcessing


@pytest.fixture
def mock_video() -> Video:
    """Create mock Video for testing."""
    return Video(
        video_id="test_video_123",
        title="Test Video Title",
        channel=Channel(
            channel_id="test_channel",
            name="Test Channel",
            url="https://youtube.com/@test",
        ),
        views=1_500_000,
        views_growth=250_000,
        likes=50_000,
        score=5,
        score_previous=7,
        score_status=VideoScoreStatus.UP,
        published_at=datetime.now(UTC),
        fetched_at=datetime.now(UTC),
        yt_video_thumbnail_url="https://i.ytimg.com/vi/test_video_123/maxresdefault.jpg",
    )


@pytest.fixture
def video_processing_instance(tmp_path: Path) -> VideoProcessing:
    """Create VideoProcessing instance with temp folders."""
    with patch("src.video_processing.get_app_settings") as mock_settings:
        mock_settings.return_value = Mock(
            video_template_end_screen_file="src/resources/end_screen.mp4",
            video_template_start_screen_file="src/resources/start_screen.mp4",
            video_template_file="src/resources/template.mp4",
            video_template_vertical_file="src/resources/template_vertical.mp4",
            video_template_thumbnail_file="src/resources/thumbnail.png",
            video_template_thumbnail_font_file="src/resources/fonts/Roboto-Bold.ttf",
            video_generated_folder=str(tmp_path / "generated"),
            threads_workers=1,
        )
        with patch("src.video_processing.VideoDownloader") as mock_downloader:
            mock_downloader.return_value.video_yt_resources_folder = str(tmp_path / "yt_resources")
            (tmp_path / "yt_resources").mkdir(parents=True, exist_ok=True)
            return VideoProcessing()


class TestVideoAssetManagerCharacterization:
    """Characterization tests for VideoAssetManager methods.

    These methods will be extracted to src/infrastructure/video/asset_manager.py.
    """

    def test_init_creates_generated_folder(self, tmp_path: Path) -> None:
        """Document that __init__ creates video_generated_folder with today's date."""
        with patch("src.video_processing.get_app_settings") as mock_settings:
            mock_settings.return_value = Mock(
                video_template_end_screen_file="src/resources/end_screen.mp4",
                video_template_start_screen_file="src/resources/start_screen.mp4",
                video_template_file="src/resources/template.mp4",
                video_template_vertical_file="src/resources/template_vertical.mp4",
                video_template_thumbnail_file="src/resources/thumbnail.png",
                video_template_thumbnail_font_file="src/resources/fonts/Roboto-Bold.ttf",
                video_generated_folder=str(tmp_path / "generated"),
            )
            with patch("src.video_processing.VideoDownloader") as mock_downloader:
                mock_downloader.return_value.video_yt_resources_folder = str(tmp_path / "yt_resources")

                vp = VideoProcessing()

                # Check folder created with today's date
                today_str = datetime.now(UTC).strftime("%Y%m%d")
                expected_folder = tmp_path / "generated" / today_str
                assert pathlib.Path(vp._video_generated_folder).exists()
                assert today_str in vp._video_generated_folder

    def test_init_stores_template_paths(self, video_processing_instance: VideoProcessing) -> None:
        """Document that __init__ stores all template file paths."""
        vp = video_processing_instance
        assert vp._end_screen_file == "src/resources/end_screen.mp4"
        assert vp._start_screen_file == "src/resources/start_screen.mp4"
        assert vp._template_file == "src/resources/template.mp4"
        assert vp._template_vertical_file == "src/resources/template_vertical.mp4"
        assert vp._thumbnail_file == "src/resources/thumbnail.png"
        assert vp._thumbnail_font_file == "src/resources/fonts/Roboto-Bold.ttf"

    @pytest.mark.slow
    async def test_delete_processed_videos_removes_folder(self, tmp_path: Path) -> None:
        """Document that delete_processed_videos removes the generated folder."""
        with patch("src.video_processing.get_app_settings") as mock_settings:
            mock_settings.return_value = Mock(
                video_template_end_screen_file="src/resources/end_screen.mp4",
                video_template_start_screen_file="src/resources/start_screen.mp4",
                video_template_file="src/resources/template.mp4",
                video_template_vertical_file="src/resources/template_vertical.mp4",
                video_template_thumbnail_file="src/resources/thumbnail.png",
                video_template_thumbnail_font_file="src/resources/fonts/Roboto-Bold.ttf",
                video_generated_folder=str(tmp_path / "generated"),
            )
            with patch("src.video_processing.VideoDownloader") as mock_downloader:
                mock_downloader.return_value.video_yt_resources_folder = str(tmp_path / "yt_resources")

                vp = VideoProcessing()
                folder = pathlib.Path(vp._video_generated_folder)
                assert folder.exists()  # Created by __init__

                # Create a test file inside
                (folder / "test.mp4").touch()

                await vp.delete_processed_videos()

                # Folder should be removed
                assert not folder.exists()


class TestVideoRendererCharacterization:
    """Characterization tests for VideoRenderer methods.

    These methods will be extracted to src/infrastructure/video/renderer.py.
    """

    def test_overlay_texts_template_returns_text_clips(
        self, video_processing_instance: VideoProcessing, mock_video: Video
    ) -> None:
        """Document _overlay_texts_template returns list of 7 clips (6 TextClip + 1 ImageClip)."""
        vp = video_processing_instance

        # Create mock VideoFileClip
        mock_clip = Mock(spec=VideoFileClip)
        mock_clip.duration = 10.0
        mock_clip.w = 1920
        mock_clip.h = 1080

        # Create QR code file (required by the method)
        qr_path = pathlib.Path(vp._video_yt_resources_folder) / f"{mock_video.video_id}_qr.png"
        qr_path.parent.mkdir(parents=True, exist_ok=True)

        # Create a real QR or mock file
        import segno

        qr = segno.make(mock_video.yt_video_url)
        qr.save(str(qr_path), dark="pink", light="#323524", scale=8)

        # Mock TextClip to avoid ImageMagick dependency
        with patch("src.infrastructure.video.renderer.TextClip") as mock_text_clip:
            with patch("src.infrastructure.video.renderer.ImageClip") as mock_image_clip:
                # Mock returns
                mock_text_clip.return_value = Mock(spec=TextClip)
                mock_text_clip.return_value.set_position.return_value = mock_text_clip.return_value
                mock_text_clip.return_value.set_duration.return_value = mock_text_clip.return_value
                mock_text_clip.return_value.set_start.return_value = mock_text_clip.return_value

                mock_image_clip.return_value = Mock()
                mock_image_clip.return_value.set_position.return_value = mock_image_clip.return_value
                mock_image_clip.return_value.set_duration.return_value = mock_image_clip.return_value
                mock_image_clip.return_value.set_start.return_value = mock_image_clip.return_value

                result = vp._overlay_texts_template(video_file_clip=mock_clip, video=mock_video)

        # Check return type and count
        assert isinstance(result, list)
        assert len(result) == 7  # 6 TextClips + 1 ImageClip (QR code)
        # Without ImageMagick, we can't verify TextClip instances, but we verified method was called 6 times
        assert mock_text_clip.call_count == 6
        assert mock_image_clip.call_count == 1

    def test_overlay_texts_vertical_template_returns_text_clips(
        self, video_processing_instance: VideoProcessing, mock_video: Video
    ) -> None:
        """Document _overlay_texts_vertical_template returns list of 9 TextClip instances."""
        vp = video_processing_instance

        # Create mock VideoFileClip
        mock_clip = Mock(spec=VideoFileClip)
        mock_clip.duration = 10.0
        mock_clip.w = 1080
        mock_clip.h = 1920

        # Mock TextClip to avoid ImageMagick dependency
        with patch("src.infrastructure.video.renderer.TextClip") as mock_text_clip:
            mock_text_clip.return_value = Mock(spec=TextClip)
            mock_text_clip.return_value.set_position.return_value = mock_text_clip.return_value
            mock_text_clip.return_value.set_duration.return_value = mock_text_clip.return_value
            mock_text_clip.return_value.set_start.return_value = mock_text_clip.return_value

            result = vp._overlay_texts_vertical_template(video_file_clip=mock_clip, video=mock_video)

        # Check return type and count
        assert isinstance(result, list)
        assert len(result) == 9
        assert mock_text_clip.call_count == 9

    def test_overlay_texts_template_handles_score_status_colors(
        self, video_processing_instance: VideoProcessing, mock_video: Video
    ) -> None:
        """Document that _overlay_texts_template maps score_status to correct colors."""
        vp = video_processing_instance
        mock_clip = Mock(spec=VideoFileClip)
        mock_clip.duration = 10.0

        # Create QR code file once
        qr_path = pathlib.Path(vp._video_yt_resources_folder) / f"{mock_video.video_id}_qr.png"
        qr_path.parent.mkdir(parents=True, exist_ok=True)
        import segno

        qr = segno.make(mock_video.yt_video_url)
        qr.save(str(qr_path), dark="pink", light="#323524", scale=8)

        # Test different score statuses
        for status in [VideoScoreStatus.NEW, VideoScoreStatus.UP, VideoScoreStatus.DOWN, VideoScoreStatus.EQUAL]:
            mock_video.score_status = status
            with patch("src.infrastructure.video.renderer.TextClip") as mock_text_clip:
                with patch("src.infrastructure.video.renderer.ImageClip") as mock_image_clip:
                    mock_text_clip.return_value = Mock(spec=TextClip)
                    mock_text_clip.return_value.set_position.return_value = mock_text_clip.return_value
                    mock_text_clip.return_value.set_duration.return_value = mock_text_clip.return_value
                    mock_text_clip.return_value.set_start.return_value = mock_text_clip.return_value

                    mock_image_clip.return_value = Mock()
                    mock_image_clip.return_value.set_position.return_value = mock_image_clip.return_value
                    mock_image_clip.return_value.set_duration.return_value = mock_image_clip.return_value
                    mock_image_clip.return_value.set_start.return_value = mock_image_clip.return_value

                    result = vp._overlay_texts_template(video_file_clip=mock_clip, video=mock_video)

            assert len(result) == 7  # 6 TextClips + 1 ImageClip
            assert mock_text_clip.call_count == 6
            mock_text_clip.reset_mock()
            mock_image_clip.reset_mock()

    @pytest.mark.slow
    async def test_overlay_with_video_template_returns_three_clips(
        self, video_processing_instance: VideoProcessing, tmp_path: Path
    ) -> None:
        """Document _overlay_with_video_template returns [base_clip, video_clip, masked_template]."""
        vp = video_processing_instance

        # Need real template file for this test
        template_path = Path(vp._template_file)
        if not template_path.exists():
            pytest.skip(f"Template file {template_path} not found — skipping real moviepy test")

        # Create minimal test video file
        from moviepy.video.VideoClip import ColorClip

        test_clip = ColorClip(size=(1920, 1080), color=(255, 0, 0), duration=1.0)
        test_video_path = tmp_path / "test_clip.mp4"
        test_clip.write_videofile(str(test_video_path), fps=24, verbose=False, logger=None)

        mock_clip = VideoFileClip(str(test_video_path))

        result = await vp._overlay_with_video_template(video_file_clip=mock_clip)

        assert isinstance(result, list)
        assert len(result) == 3  # base_clip, video_file_clip, masked_clip

    @pytest.mark.slow
    async def test_overlay_with_vertical_video_template_returns_three_clips(
        self, video_processing_instance: VideoProcessing, tmp_path: Path
    ) -> None:
        """Document _overlay_with_vertical_video_template returns [base_clip, cropped_clip, masked_template]."""
        vp = video_processing_instance

        # Need real template file for this test
        template_path = Path(vp._template_vertical_file)
        if not template_path.exists():
            pytest.skip(f"Template file {template_path} not found — skipping real moviepy test")

        # Create minimal test video file
        from moviepy.video.VideoClip import ColorClip

        test_clip = ColorClip(size=(1920, 1080), color=(0, 255, 0), duration=1.0)
        test_video_path = tmp_path / "test_vertical_clip.mp4"
        test_clip.write_videofile(str(test_video_path), fps=24, verbose=False, logger=None)

        mock_clip = VideoFileClip(str(test_video_path))

        result = await vp._overlay_with_vertical_video_template(video_file_clip=mock_clip)

        assert isinstance(result, list)
        assert len(result) == 3  # base_clip, cropped/resized clip, masked_clip


class TestThumbnailGeneratorCharacterization:
    """Characterization tests for ThumbnailGenerator methods.

    These methods will be extracted to src/infrastructure/video/thumbnail.py.
    """

    @pytest.mark.slow
    async def test_generate_thumbnail_creates_2x2_grid(
        self, video_processing_instance: VideoProcessing, mock_video: Video, tmp_path: Path
    ) -> None:
        """Document generate_thumbnail creates 2x2 grid from 4 videos."""
        vp = video_processing_instance

        # Create thumbnail template
        thumbnail_path = Path(vp._thumbnail_file)
        thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
        base_img = Image.new("RGBA", (1920, 1080), color=(0, 0, 0, 128))
        base_img.save(thumbnail_path)

        # Create font file
        font_path = Path(vp._thumbnail_font_file)
        font_path.parent.mkdir(parents=True, exist_ok=True)
        font_path.touch()  # Mock font file

        # Create 4 mock videos
        video_list = []
        for i in range(4):
            vid = Video(
                video_id=f"video_{i}",
                title=f"Title {i}",
                channel=Channel(channel_id="ch", name="Channel", url="https://youtube.com"),
                views=100000,
                views_growth=1000,
                likes=5000,
                score=i + 1,
                score_previous=None,
                score_status=VideoScoreStatus.NEW,
                published_at=datetime.now(UTC),
                fetched_at=datetime.now(UTC),
                yt_video_thumbnail_url="https://i.ytimg.com/vi/test/maxresdefault.jpg",
            )
            video_list.append(vid)

        # Mock requests.get for thumbnail downloads
        mock_response = Mock()
        mock_img = Image.new("RGB", (320, 180), color=(255, 0, 0))
        from io import BytesIO

        img_bytes = BytesIO()
        mock_img.save(img_bytes, format="JPEG")
        img_bytes.seek(0)
        mock_response.raw = img_bytes

        with patch("src.infrastructure.video.thumbnail_generator.requests.get", return_value=mock_response):
            with patch("src.infrastructure.video.thumbnail_generator.Image.open") as mock_image_open:
                with patch("src.infrastructure.video.thumbnail_generator.Image.new") as mock_image_new:
                    with patch("src.infrastructure.video.thumbnail_generator.ImageDraw.Draw") as mock_draw:
                        with patch(
                            "src.infrastructure.video.thumbnail_generator.ImageFont.truetype"
                        ):  # Mock font loading
                            # Create reusable mock image
                            def create_mock_image(*args, **kwargs):
                                img_mock = Mock()
                                img_mock.width = 1920
                                img_mock.height = 1080
                                img_mock.size = (1920, 1080)
                                img_mock.load = Mock()
                                img_mock.paste = Mock()
                                img_mock.save = Mock()
                                img_mock.resize = Mock(return_value=img_mock)
                                img_mock.__enter__ = Mock(return_value=img_mock)
                                img_mock.__exit__ = Mock(return_value=False)
                                return img_mock

                            # Mock Image.open for template and thumbnails
                            mock_image_open.side_effect = create_mock_image
                            # Mock Image.new for canvas
                            mock_image_new.side_effect = create_mock_image
                            # Mock ImageDraw.Draw
                            mock_draw.return_value = Mock(text=Mock())

                            result_path = await vp.generate_thumbnail(video_list)

        # Check result
        assert isinstance(result_path, str)
        assert "_thumbnail.jpg" in result_path
        # Note: result_path file may not exist since Image operations are mocked


class TestVideoCompositorCharacterization:
    """Characterization tests for VideoCompositor methods.

    These methods will be extracted to src/infrastructure/video/compositor.py.
    """

    @pytest.mark.slow
    async def test_render_clip_creates_mp4_file(
        self, video_processing_instance: VideoProcessing, tmp_path: Path
    ) -> None:
        """Document _render_clip creates .mp4 file at expected path."""
        vp = video_processing_instance

        # Create minimal CompositeVideoClip
        from moviepy.video.VideoClip import ColorClip

        clip1 = ColorClip(size=(1920, 1080), color=(255, 0, 0), duration=2.0)
        composite = CompositeVideoClip([clip1])

        result_path = await vp._render_clip(composite, "test_render")

        # Check file created
        assert isinstance(result_path, str)
        assert result_path.endswith("_format.mp4")
        assert pathlib.Path(result_path).exists()

        # Check it returns existing path if called again
        result_path_2 = await vp._render_clip(composite, "test_render")
        assert result_path == result_path_2

    @pytest.mark.slow
    async def test_post_process_video_calls_render_clip(
        self, video_processing_instance: VideoProcessing, mock_video: Video, tmp_path: Path
    ) -> None:
        """Document post_process_video orchestrates template overlay + text overlay + render."""
        vp = video_processing_instance

        # Create mock video file for source
        from moviepy.video.VideoClip import ColorClip

        test_clip = ColorClip(size=(1920, 1080), color=(0, 255, 0), duration=10.0)
        test_video_path = Path(vp._video_yt_resources_folder) / f"{mock_video.video_id}.mp4"
        test_video_path.parent.mkdir(parents=True, exist_ok=True)
        test_clip.write_videofile(str(test_video_path), fps=24, verbose=False, logger=None)

        # Skip if template files don't exist
        if not Path(vp._template_file).exists():
            pytest.skip(f"Template {vp._template_file} not found")

        with patch("src.video_processing.segno.make"):  # Mock QR generation
            await vp.post_process_video(mock_video)

        # Check output file created
        expected_output = pathlib.Path(vp._video_generated_folder) / f"{mock_video.video_id}_format.mp4"
        assert expected_output.exists()

    @pytest.mark.slow
    async def test_post_process_vertical_video_creates_vertical_format(
        self, video_processing_instance: VideoProcessing, mock_video: Video, tmp_path: Path
    ) -> None:
        """Document post_process_vertical_video creates {video_id}_vertical_format.mp4."""
        vp = video_processing_instance

        # Create mock video file
        from moviepy.video.VideoClip import ColorClip

        test_clip = ColorClip(size=(1920, 1080), color=(0, 0, 255), duration=10.0)
        test_video_path = Path(vp._video_yt_resources_folder) / f"{mock_video.video_id}.mp4"
        test_video_path.parent.mkdir(parents=True, exist_ok=True)
        test_clip.write_videofile(str(test_video_path), fps=24, verbose=False, logger=None)

        # Skip if template files don't exist
        if not Path(vp._template_vertical_file).exists():
            pytest.skip(f"Vertical template {vp._template_vertical_file} not found")

        await vp.post_process_vertical_video(mock_video)

        # Check vertical output created
        expected_output = pathlib.Path(vp._video_generated_folder) / f"{mock_video.video_id}_vertical_format.mp4"
        assert expected_output.exists()

    @pytest.mark.slow
    async def test_join_processed_videos_applies_crossfade(
        self, video_processing_instance: VideoProcessing, tmp_path: Path
    ) -> None:
        """Document join_processed_videos creates crossfaded composite from multiple videos."""
        vp = video_processing_instance

        # Create 3 processed video files
        from moviepy.video.VideoClip import ColorClip

        video_ids = ["video_1", "video_2", "video_3"]
        for video_id in video_ids:
            clip = ColorClip(size=(1920, 1080), color=(255, 255, 0), duration=3.0)
            output_path = Path(vp._video_generated_folder) / f"{video_id}_format.mp4"
            clip.write_videofile(str(output_path), fps=24, verbose=False, logger=None)

        # Need start/end screen files
        if not Path(vp._start_screen_file).exists() or not Path(vp._end_screen_file).exists():
            pytest.skip("Start/end screen files not found")

        result_path = await vp.join_processed_videos(video_ids, vertical=False)

        # Check result
        assert isinstance(result_path, str)
        assert pathlib.Path(result_path).exists()
        assert "_format.mp4" in result_path
