"""Characterization tests for VideoCompositor before MoviePy 2 migration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

from src.domain.models import Channel, Video
from src.infrastructure.video.asset_manager import VideoAssetManager
from src.infrastructure.video.compositor import VideoCompositor
from src.infrastructure.video.renderer import VideoRenderer


class _RecordedVideoClip:
    def __init__(self, filename: str, *, duration: float, width: int = 1920, height: int = 1080) -> None:
        self.filename = filename
        self.duration = duration
        self.w = width
        self.h = height
        self.width = width
        self.height = height
        self.start = 0.0
        self.end = duration
        self.operations: list[tuple[str, object]] = []
        self.write_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def set_position(self, value: object) -> _RecordedVideoClip:
        self.operations.append(("position", value))
        return self

    def with_position(self, value: object) -> _RecordedVideoClip:
        return self.set_position(value)

    def set_start(self, value: float) -> _RecordedVideoClip:
        self.start = value
        self.end = value + self.duration
        self.operations.append(("start", value))
        return self

    def with_start(self, value: float) -> _RecordedVideoClip:
        return self.set_start(value)

    def subclip(self, *, t_start: float, t_end: float) -> _RecordedVideoClip:
        self.duration = t_end - t_start
        self.end = self.start + self.duration
        self.operations.append(("subclip", (t_start, t_end)))
        return self

    def subclipped(self, start_time: float = 0, end_time: float | None = None) -> _RecordedVideoClip:
        effective_end = self.duration if end_time is None else end_time
        return self.subclip(t_start=start_time, t_end=effective_end)

    def fx(self, effect: object, *args: object, **kwargs: object) -> _RecordedVideoClip:
        self.operations.append(("fx", (effect, args, kwargs)))
        return self

    def with_effects(self, effects: list[object]) -> _RecordedVideoClip:
        self.operations.append(("effects", effects))
        return self

    def write_videofile(self, *args: object, **kwargs: object) -> None:
        self.write_calls.append((args, kwargs))

    def close(self) -> None:
        self.operations.append(("close", None))


class _RecordedCompositeClip(_RecordedVideoClip):
    def __init__(self, clips: list[object]) -> None:
        self.clips = clips
        super().__init__("composite", duration=0.0)


def _make_asset_manager(tmp_path: Path) -> VideoAssetManager:
    return VideoAssetManager(
        end_screen_file=str(tmp_path / "end.mp4"),
        start_screen_file=str(tmp_path / "start.mp4"),
        template_file=str(tmp_path / "template.mp4"),
        template_vertical_file=str(tmp_path / "template_vertical.mp4"),
        thumbnail_file=str(tmp_path / "thumb.png"),
        thumbnail_font_file=str(tmp_path / "font.ttf"),
        video_yt_resources_folder=str(tmp_path / "yt"),
        video_generated_base_folder=str(tmp_path / "generated"),
    )


def _make_video(video_id: str = "abc123") -> Video:
    return Video(
        video_id=video_id,
        score=5,
        title="Example song",
        channel=Channel(name="Test Channel"),
    )


class TestVideoCompositor:
    def test_source_video_file_accepts_non_mp4_extension(self, tmp_path: Path) -> None:
        asset_manager = _make_asset_manager(tmp_path)
        yt_folder = Path(asset_manager.video_yt_resources_folder)
        yt_folder.mkdir(parents=True, exist_ok=True)
        source_file = yt_folder / "abc123.webm"
        source_file.touch()

        compositor = VideoCompositor(asset_manager, VideoRenderer(asset_manager))

        resolved = compositor._source_video_file(_make_video())

        assert resolved == source_file

    async def test_post_process_video_trims_middle_segment_for_long_clips(self, tmp_path: Path, monkeypatch) -> None:
        (tmp_path / "yt").mkdir(parents=True, exist_ok=True)
        (tmp_path / "yt" / "abc123.mp4").touch()
        source_clip = _RecordedVideoClip(str(tmp_path / "yt" / "abc123.mp4"), duration=60.0)
        composite_clips: list[_RecordedCompositeClip] = []

        monkeypatch.setattr("src.infrastructure.video.compositor.VideoFileClip", lambda *args, **kwargs: source_clip)
        monkeypatch.setattr(
            "src.infrastructure.video.compositor.CompositeVideoClip",
            lambda clips: composite_clips.append(_RecordedCompositeClip(clips)) or composite_clips[-1],
        )

        renderer = VideoRenderer(_make_asset_manager(tmp_path))
        monkeypatch.setattr(renderer, "overlay_with_video_template", AsyncMock(return_value=["base", "overlay"]))
        monkeypatch.setattr(renderer, "overlay_texts_template", lambda **_kwargs: ["text1", "text2"])

        compositor = VideoCompositor(_make_asset_manager(tmp_path), renderer)
        compositor._render_clip = AsyncMock(return_value="/tmp/output.mp4")  # type: ignore[method-assign]

        await compositor.post_process_video(_make_video())

        assert ("subclip", (30, 38)) in source_clip.operations
        renderer.overlay_with_video_template.assert_awaited_once()
        compositor._render_clip.assert_awaited_once_with(composite_clips[0], "abc123")
        assert composite_clips[0].clips == ["base", "overlay", "text1", "text2"]

    async def test_post_process_vertical_video_uses_top_alignment_and_short_trim(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        (tmp_path / "yt").mkdir(parents=True, exist_ok=True)
        (tmp_path / "yt" / "abc123.mp4").touch()
        source_clip = _RecordedVideoClip(str(tmp_path / "yt" / "abc123.mp4"), duration=12.0, width=1080, height=1920)
        composite_clips: list[_RecordedCompositeClip] = []

        monkeypatch.setattr("src.infrastructure.video.compositor.VideoFileClip", lambda *args, **kwargs: source_clip)
        monkeypatch.setattr(
            "src.infrastructure.video.compositor.CompositeVideoClip",
            lambda clips: composite_clips.append(_RecordedCompositeClip(clips)) or composite_clips[-1],
        )

        renderer = VideoRenderer(_make_asset_manager(tmp_path))
        monkeypatch.setattr(
            renderer, "overlay_with_vertical_video_template", AsyncMock(return_value=["base", "overlay"])
        )
        monkeypatch.setattr(renderer, "overlay_texts_vertical_template", lambda **_kwargs: ["text"])

        compositor = VideoCompositor(_make_asset_manager(tmp_path), renderer)
        compositor._render_clip = AsyncMock(return_value="/tmp/output_vertical.mp4")  # type: ignore[method-assign]

        await compositor.post_process_vertical_video(_make_video())

        assert ("position", "top") in source_clip.operations
        assert ("subclip", (0, 8)) in source_clip.operations
        compositor._render_clip.assert_awaited_once_with(composite_clips[0], "abc123_vertical")
        assert composite_clips[0].clips == ["base", "overlay", "text"]

    async def test_join_processed_videos_adds_bookend_clips(self, tmp_path: Path, monkeypatch) -> None:
        created_clips: list[_RecordedVideoClip] = []
        composite_clips: list[_RecordedCompositeClip] = []

        def build_clip(filename: str, *args: object, **kwargs: object) -> _RecordedVideoClip:
            clip = _RecordedVideoClip(filename, duration=8.0)
            created_clips.append(clip)
            return clip

        monkeypatch.setattr("src.infrastructure.video.compositor.VideoFileClip", build_clip)
        monkeypatch.setattr(
            "src.infrastructure.video.compositor.CompositeVideoClip",
            lambda clips: composite_clips.append(_RecordedCompositeClip(clips)) or composite_clips[-1],
        )
        monkeypatch.setattr("src.infrastructure.video.compositor.clip_with_crossfade_in", lambda clip, _duration: clip)

        renderer = VideoRenderer(_make_asset_manager(tmp_path))
        compositor = VideoCompositor(_make_asset_manager(tmp_path), renderer)
        compositor._render_clip = AsyncMock(return_value="/tmp/joined.mp4")  # type: ignore[method-assign]

        result = await compositor.join_processed_videos(["v1", "v2"])

        assert result == "/tmp/joined.mp4"
        assert len(created_clips) == 4
        assert composite_clips[0].clips[0] is created_clips[0]
        assert composite_clips[0].clips[-1] is created_clips[-1]
        compositor._render_clip.assert_awaited_once()

    async def test_render_clip_skips_existing_output(self, tmp_path: Path) -> None:
        renderer = VideoRenderer(_make_asset_manager(tmp_path))
        compositor = VideoCompositor(_make_asset_manager(tmp_path), renderer)
        output_path = Path(compositor._video_generated_folder) / "existing_format.mp4"
        output_path.touch()
        clip = _RecordedCompositeClip([])

        result = await compositor._render_clip(clip, "existing")

        assert result == str(output_path)
        assert clip.write_calls == []

    async def test_render_clip_uses_expected_encoding_parameters(self, tmp_path: Path, monkeypatch) -> None:
        renderer = VideoRenderer(_make_asset_manager(tmp_path))
        compositor = VideoCompositor(_make_asset_manager(tmp_path), renderer)
        clip = _RecordedCompositeClip([])

        class _Settings:
            threads_workers = None

        monkeypatch.setattr("src.infrastructure.video.compositor.get_app_settings", lambda: _Settings())

        result = await compositor._render_clip(clip, "fresh")

        assert result.endswith("fresh_format.mp4")
        assert len(clip.write_calls) == 1
        _args, kwargs = clip.write_calls[0]
        assert kwargs["remove_temp"] is True
        assert kwargs["fps"] == 24
        assert kwargs["codec"] == "libx264"
        assert kwargs["threads"] == 1
        assert kwargs["preset"] == "ultrafast"
