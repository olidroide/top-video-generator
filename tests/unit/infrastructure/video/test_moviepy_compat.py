"""Tests for the MoviePy compatibility helpers against the installed backend."""

from __future__ import annotations

from src.infrastructure.video.moviepy_compat import (
    IS_MOVIEPY_V2,
    ColorClip,
    build_text_clip,
    clip_cropped,
    clip_mask_color,
    clip_resized,
    clip_with_duration,
    clip_with_position,
    clip_with_start,
)


class TestMoviePyCompat:
    def test_text_clip_helpers_work_with_installed_backend(self) -> None:
        clip = build_text_clip(
            "Hello",
            font="DejaVu Sans Mono",
            font_size=24,
            color="white",
            size=(240, 80),
            align="center",
            method="caption",
        )
        clip = clip_with_position(clip, (10, 20))
        clip = clip_with_duration(clip, 3.5)
        clip = clip_with_start(clip, 0)

        assert IS_MOVIEPY_V2 is True
        assert clip.duration == 3.5
        assert clip.pos(0) == (10, 20)

        clip.close()

    def test_effect_helpers_work_with_installed_backend(self) -> None:
        clip = ColorClip(size=(100, 100), color=(0, 0, 255), duration=1)
        masked = clip_mask_color(clip, color=(0, 0, 255), threshold=10, stiffness=2)
        resized = clip_resized(masked, width=50, height=50)
        cropped = clip_cropped(resized, x1=5)

        assert cropped.w == 45
        assert cropped.h == 50

        for value in (cropped, resized, masked, clip):
            value.close()
