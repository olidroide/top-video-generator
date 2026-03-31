"""Unit tests for ThumbnailGenerator."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image

from src.domain.models import Channel, Video
from src.infrastructure.video.asset_manager import VideoAssetManager
from src.infrastructure.video.thumbnail_generator import ThumbnailGenerator


def _make_video(video_id: str, score: int) -> Video:
    return Video(
        video_id=video_id,
        score=score,
        title=f"Video {video_id}",
        channel=Channel(name="Test Channel"),
    )


def _make_png_bytes(color: tuple[int, int, int]) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (64, 64), color=color).save(buffer, format="PNG")
    return buffer.getvalue()


class TestThumbnailGenerator:
    async def test_generate_thumbnail_uses_thumbnail_base_asset(self, tmp_path: Path, monkeypatch) -> None:
        thumbnail_base = tmp_path / "thumbnail_base.png"
        Image.new("RGBA", (1200, 1000), (0, 0, 0, 0)).save(thumbnail_base)

        asset_manager = VideoAssetManager(
            end_screen_file="",
            start_screen_file="",
            template_file=str(tmp_path / "missing_template.png"),
            template_vertical_file="",
            thumbnail_file=str(thumbnail_base),
            thumbnail_font_file=str(tmp_path / "unused_font.ttf"),
            video_yt_resources_folder=str(tmp_path / "yt"),
            video_generated_base_folder=str(tmp_path / "generated"),
        )

        thumbnail_bytes = _make_png_bytes((255, 0, 0))
        monkeypatch.setattr(
            ThumbnailGenerator,
            "_fetch_thumbnail_bytes",
            staticmethod(lambda _url: thumbnail_bytes),
        )
        monkeypatch.setattr(
            "src.infrastructure.video.thumbnail_generator.ImageFont.truetype",
            lambda *_args, **_kwargs: object(),
        )
        monkeypatch.setattr(
            "src.infrastructure.video.thumbnail_generator.ImageDraw.ImageDraw.text",
            lambda *_args, **_kwargs: None,
        )

        generator = ThumbnailGenerator(asset_manager)
        output_path = await generator.generate_thumbnail(
            [
                _make_video("a", 1),
                _make_video("b", 2),
                _make_video("c", 3),
                _make_video("d", 4),
            ]
        )

        assert Path(output_path).exists()
