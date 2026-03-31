"""Characterization tests for VideoRenderer before MoviePy 2 migration."""

from __future__ import annotations

from pathlib import Path

from src.domain.models import Channel, Video, VideoScoreStatus
from src.infrastructure.video.asset_manager import VideoAssetManager
from src.infrastructure.video.renderer import VideoRenderer


class _RecordedClip:
    def __init__(self, kind: str, args: tuple[object, ...], kwargs: dict[str, object]) -> None:
        self.kind = kind
        self.args = args
        self.kwargs = kwargs
        self.operations: list[tuple[str, object]] = []
        self.duration: float | None = None
        self.start: float | None = None
        self.position: object | None = None

    @property
    def text(self) -> object | None:
        if "text" in self.kwargs:
            return self.kwargs["text"]
        if self.args:
            return self.args[0]
        return None

    def set_position(self, value: object) -> _RecordedClip:
        self.position = value
        self.operations.append(("position", value))
        return self

    def with_position(self, value: object) -> _RecordedClip:
        return self.set_position(value)

    def set_pos(self, value: object) -> _RecordedClip:
        return self.set_position(value)

    def with_pos(self, value: object) -> _RecordedClip:
        return self.set_position(value)

    def set_duration(self, value: float) -> _RecordedClip:
        self.duration = value
        self.operations.append(("duration", value))
        return self

    def with_duration(self, value: float) -> _RecordedClip:
        return self.set_duration(value)

    def set_start(self, value: float) -> _RecordedClip:
        self.start = value
        self.operations.append(("start", value))
        return self

    def with_start(self, value: float) -> _RecordedClip:
        return self.set_start(value)

    def fx(self, effect: object, *args: object, **kwargs: object) -> _RecordedClip:
        self.operations.append(("fx", (effect, args, kwargs)))
        return self

    def with_effects(self, effects: list[object]) -> _RecordedClip:
        self.operations.append(("effects", effects))
        return self


class _RecordedQrCode:
    def __init__(self) -> None:
        self.saved_paths: list[str] = []

    def save(self, path: str, **_kwargs: object) -> None:
        self.saved_paths.append(path)


class _DummySourceClip:
    def __init__(self, *, duration: float, width: int = 1920, height: int = 1080) -> None:
        self.duration = duration
        self.w = width
        self.h = height
        self.width = width
        self.height = height


def _make_asset_manager(tmp_path: Path) -> VideoAssetManager:
    return VideoAssetManager(
        end_screen_file="end.mp4",
        start_screen_file="start.mp4",
        template_file=str(tmp_path / "template.mp4"),
        template_vertical_file=str(tmp_path / "template_vertical.mp4"),
        thumbnail_file=str(tmp_path / "thumb.png"),
        thumbnail_font_file=str(tmp_path / "font.ttf"),
        video_yt_resources_folder=str(tmp_path / "yt"),
        video_generated_base_folder=str(tmp_path / "generated"),
    )


def _make_video() -> Video:
    return Video(
        video_id="abc123",
        views=1234567,
        views_growth=98765,
        score=7,
        score_status=VideoScoreStatus.UP,
        score_previous=9,
        title="My Song Official Video - #Video (Music Video)",
        channel=Channel(name="Test Channel"),
    )


class TestVideoRenderer:
    def test_overlay_texts_template_builds_expected_horizontal_clips(self, tmp_path: Path, monkeypatch) -> None:
        created_text_clips: list[_RecordedClip] = []
        created_image_clips: list[_RecordedClip] = []
        qr_code = _RecordedQrCode()

        monkeypatch.setattr(
            "src.infrastructure.video.renderer.build_text_clip",
            lambda *args, **kwargs: (
                created_text_clips.append(_RecordedClip("text", args, kwargs)) or created_text_clips[-1]
            ),
        )
        monkeypatch.setattr(
            "src.infrastructure.video.renderer.build_image_clip",
            lambda *args, **kwargs: (
                created_image_clips.append(_RecordedClip("image", args, kwargs)) or created_image_clips[-1]
            ),
        )
        monkeypatch.setattr("src.infrastructure.video.renderer.segno.make", lambda _url: qr_code)

        renderer = VideoRenderer(_make_asset_manager(tmp_path))
        clips = renderer.overlay_texts_template(_DummySourceClip(duration=8.0), _make_video())

        assert len(clips) == 7
        assert len(created_text_clips) == 6
        assert len(created_image_clips) == 1
        assert created_text_clips[0].text == "07"
        assert created_text_clips[2].text == "My Song"
        assert created_text_clips[3].text == "© Test Channel"
        assert created_text_clips[4].text == "1.23M"
        assert created_text_clips[5].text == "98.77k"
        assert created_text_clips[0].position == (190, 705)
        assert all(clip.duration == 8.0 for clip in created_text_clips)
        assert all(clip.start == 0 for clip in created_text_clips)
        assert created_image_clips[0].position == (1498, 688)
        assert created_image_clips[0].duration == 8.0
        assert qr_code.saved_paths == [str(tmp_path / "yt" / "abc123_qr.png")]

    def test_overlay_texts_vertical_template_builds_expected_vertical_clips(self, tmp_path: Path, monkeypatch) -> None:
        created_text_clips: list[_RecordedClip] = []

        monkeypatch.setattr(
            "src.infrastructure.video.renderer.build_text_clip",
            lambda *args, **kwargs: (
                created_text_clips.append(_RecordedClip("text", args, kwargs)) or created_text_clips[-1]
            ),
        )

        renderer = VideoRenderer(_make_asset_manager(tmp_path))
        video = _make_video()
        video.title = "An Extremely Long Title Full Song Official Video: Live Version"
        clips = renderer.overlay_texts_vertical_template(_DummySourceClip(duration=12.5), video)

        assert len(clips) == 9
        assert len(created_text_clips) == 9
        assert created_text_clips[0].text == "07"
        assert created_text_clips[2].text == "9"
        assert created_text_clips[3].text == video.yt_video_title_cleaned[:38]
        assert created_text_clips[5].text == "1.23M"
        assert created_text_clips[7].text == "98.77k"
        assert created_text_clips[5].position == (83, 1400)
        assert created_text_clips[7].position == (400, 1400)
        assert all(clip.duration == 12.5 for clip in created_text_clips)
        assert all(clip.start == 0 for clip in created_text_clips)
