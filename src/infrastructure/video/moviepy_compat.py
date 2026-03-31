"""Compatibility helpers for MoviePy 1.x and 2.x APIs."""

from __future__ import annotations

import inspect
from importlib import import_module
from pathlib import Path
from typing import Any, Final

try:
    moviepy = import_module("moviepy")
    ColorClip = moviepy.ColorClip
    CompositeVideoClip = moviepy.CompositeVideoClip
    ImageClip = moviepy.ImageClip
    TextClip = moviepy.TextClip
    VideoFileClip = moviepy.VideoFileClip
    AudioFadeOut = import_module("moviepy.audio.fx.AudioFadeOut").AudioFadeOut
    CrossFadeIn = import_module("moviepy.video.fx.CrossFadeIn").CrossFadeIn
    MaskColor = import_module("moviepy.video.fx.MaskColor").MaskColor
    _is_moviepy_v2 = True
except ImportError:
    ColorClip = import_module("moviepy.video.VideoClip").ColorClip
    CompositeVideoClip = import_module("moviepy.video.compositing.CompositeVideoClip").CompositeVideoClip
    ImageClip = import_module("moviepy.video.VideoClip").ImageClip
    TextClip = import_module("moviepy.video.VideoClip").TextClip
    VideoFileClip = import_module("moviepy.video.io.VideoFileClip").VideoFileClip
    audio_fadeout = import_module("moviepy.audio.fx.audio_fadeout").audio_fadeout
    crop = import_module("moviepy.video.fx.crop").crop
    mask_color = import_module("moviepy.video.fx.mask_color").mask_color
    resize = import_module("moviepy.video.fx.resize").resize
    _is_moviepy_v2 = False

IS_MOVIEPY_V2: Final[bool] = _is_moviepy_v2

type MoviePyClip = Any

__all__ = [
    "IS_MOVIEPY_V2",
    "ColorClip",
    "CompositeVideoClip",
    "ImageClip",
    "MoviePyClip",
    "TextClip",
    "VideoFileClip",
    "build_image_clip",
    "build_text_clip",
    "clip_cropped",
    "clip_mask_color",
    "clip_resized",
    "clip_subclipped",
    "clip_with_audio_fade_out",
    "clip_with_crossfade_in",
    "clip_with_duration",
    "clip_with_position",
    "clip_with_start",
    "close_clip",
    "video_target_resolution",
]

_TEXTCLIP_PARAMETERS = frozenset(inspect.signature(TextClip).parameters)
_IMAGECLIP_PARAMETERS = frozenset(inspect.signature(ImageClip).parameters)

_FONT_FALLBACKS: dict[str, tuple[str, ...]] = {
    "DejaVu Sans Mono": (
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/Library/Fonts/Menlo.ttc",
        "/System/Library/Fonts/Menlo.ttc",
    ),
    "Liberation Sans": (
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ),
}


def _resolve_font(font: str | None) -> str | None:
    if not font or not IS_MOVIEPY_V2:
        return font

    font_path = Path(font)
    if font_path.exists():
        return str(font_path)

    for candidate in _FONT_FALLBACKS.get(font, ()):
        if Path(candidate).exists():
            return candidate

    return None


def _normalize_text_align(align: str | None) -> str:
    if not align:
        return "left"

    normalized = align.lower()
    return {
        "west": "left",
        "east": "right",
        "center": "center",
        "left": "left",
        "right": "right",
    }.get(normalized, "left")


def _build_text_kwargs(
    *,
    font: str | None,
    font_size: int,
    color: str,
    stroke_color: str | None,
    stroke_width: int,
    size: tuple[int, int] | None,
    method: str | None,
    kerning: int | None,
) -> dict[str, object]:
    kwargs: dict[str, object] = {"color": color}
    resolved_font = _resolve_font(font)

    if "font" in _TEXTCLIP_PARAMETERS:
        kwargs["font"] = resolved_font

    if "font_size" in _TEXTCLIP_PARAMETERS:
        kwargs["font_size"] = font_size
    elif "fontsize" in _TEXTCLIP_PARAMETERS:
        kwargs["fontsize"] = font_size

    if stroke_color is not None and "stroke_color" in _TEXTCLIP_PARAMETERS:
        kwargs["stroke_color"] = stroke_color
    if "stroke_width" in _TEXTCLIP_PARAMETERS:
        kwargs["stroke_width"] = stroke_width
    if size is not None and "size" in _TEXTCLIP_PARAMETERS:
        kwargs["size"] = size
    if method is not None and "method" in _TEXTCLIP_PARAMETERS:
        kwargs["method"] = method
    if kerning is not None and "kerning" in _TEXTCLIP_PARAMETERS:
        kwargs["kerning"] = kerning

    return kwargs


def _build_alignment_kwargs(align: str | None) -> dict[str, object]:
    if align is not None and "align" in _TEXTCLIP_PARAMETERS:
        return {"align": align}

    normalized_align = _normalize_text_align(align)
    kwargs: dict[str, object] = {}
    if "text_align" in _TEXTCLIP_PARAMETERS:
        kwargs["text_align"] = normalized_align
    if "horizontal_align" in _TEXTCLIP_PARAMETERS:
        kwargs["horizontal_align"] = normalized_align
    return kwargs


def build_text_clip(
    text: str,
    *,
    font: str | None,
    font_size: int,
    color: str,
    stroke_color: str | None = None,
    stroke_width: int = 0,
    size: tuple[int, int] | None = None,
    align: str | None = None,
    method: str | None = None,
    kerning: int | None = None,
) -> MoviePyClip:
    args: list[object] = []
    kwargs: dict[str, object] = {}

    if "text" in _TEXTCLIP_PARAMETERS:
        kwargs["text"] = text
    else:
        args.append(text)

    kwargs.update(
        _build_text_kwargs(
            font=font,
            font_size=font_size,
            color=color,
            stroke_color=stroke_color,
            stroke_width=stroke_width,
            size=size,
            method=method,
            kerning=kerning,
        )
    )
    kwargs.update(_build_alignment_kwargs(align))

    return TextClip(*args, **kwargs)


def build_image_clip(image: str, *, is_mask: bool = False) -> MoviePyClip:
    kwargs: dict[str, object] = {}
    if "ismask" in _IMAGECLIP_PARAMETERS:
        kwargs["ismask"] = is_mask
    elif "is_mask" in _IMAGECLIP_PARAMETERS:
        kwargs["is_mask"] = is_mask
    return ImageClip(image, **kwargs)


def clip_with_duration(clip: MoviePyClip, duration: float) -> MoviePyClip:
    if hasattr(clip, "with_duration"):
        return clip.with_duration(duration)
    return clip.set_duration(duration)


def clip_with_start(clip: MoviePyClip, start: float) -> MoviePyClip:
    if hasattr(clip, "with_start"):
        return clip.with_start(start)
    return clip.set_start(start)


def clip_with_position(clip: MoviePyClip, position: object) -> MoviePyClip:
    if hasattr(clip, "with_position"):
        return clip.with_position(position)
    if hasattr(clip, "set_position"):
        return clip.set_position(position)
    return clip.set_pos(position)


def clip_subclipped(clip: MoviePyClip, start_time: float, end_time: float) -> MoviePyClip:
    if hasattr(clip, "subclipped"):
        return clip.subclipped(start_time, end_time)
    return clip.subclip(t_start=start_time, t_end=end_time)


def clip_mask_color(
    clip: MoviePyClip,
    *,
    color: tuple[int, int, int],
    threshold: float,
    stiffness: float,
) -> MoviePyClip:
    if IS_MOVIEPY_V2:
        return clip.with_effects([MaskColor(color=color, threshold=threshold, stiffness=stiffness)])
    return clip.fx(mask_color, color=list(color), thr=threshold, s=stiffness)


def clip_cropped(clip: MoviePyClip, *, x1: int | None = None) -> MoviePyClip:
    if hasattr(clip, "cropped"):
        return clip.cropped(x1=x1)
    return clip.fx(crop, x1=x1)


def clip_resized(clip: MoviePyClip, *, width: float | None = None, height: float | None = None) -> MoviePyClip:
    if hasattr(clip, "resized"):
        return clip.resized(width=width, height=height)
    return clip.fx(resize, width=width, height=height)


def clip_with_audio_fade_out(clip: MoviePyClip, duration: float) -> MoviePyClip:
    if IS_MOVIEPY_V2:
        return clip.with_effects([AudioFadeOut(duration)])
    return clip.fx(audio_fadeout, duration)


def clip_with_crossfade_in(clip: MoviePyClip, duration: float) -> MoviePyClip:
    if IS_MOVIEPY_V2:
        return clip.with_effects([CrossFadeIn(duration)])
    crossfadein = import_module("moviepy.video.compositing.transitions").crossfadein
    return crossfadein(clip, duration)


def video_target_resolution(width: int, height: int) -> tuple[int, int]:
    if IS_MOVIEPY_V2:
        return (width, height)
    return (height, width)


def close_clip(clip: MoviePyClip | None) -> None:
    if clip is None:
        return
    close = getattr(clip, "close", None)
    if callable(close):
        close()
