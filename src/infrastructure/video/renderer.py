# pyright: reportMissingTypeStubs=false

"""Video Renderer - text overlays, templates, and clip composition.

Part of C1 split (video_processing.py -> infrastructure/video/).
Extracted: March 8, 2026 - Phase 4 hexagonal architecture.

This module handles all video rendering operations:
- Text overlay generation (score, title, channel, views)
- Template masking and composition
- Font path resolution and fallback
- QR code generation for video URLs

Dependencies: VideoAssetManager (paths), moviepy, segno
"""

import pathlib
from typing import TYPE_CHECKING

import segno
from millify import millify
from moviepy.Clip import Clip as MoviePyClip
from moviepy.video.fx.crop import crop
from moviepy.video.fx.mask_color import mask_color
from moviepy.video.fx.resize import resize
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.VideoClip import ColorClip, ImageClip, TextClip

from src.domain.models import Video, VideoScoreStatus
from src.shared.logging import get_logger

if TYPE_CHECKING:
    from src.infrastructure.video.asset_manager import VideoAssetManager

logger = get_logger(__name__)


class VideoRenderer:
    """Renders text overlays and applies templates to video clips.

    Responsibilities:
    - Generate text overlays (score, title, views, channel)
    - Apply horizontal/vertical templates with masking
    - Create QR codes for video URLs
    - Font path resolution with fallbacks

    Does NOT:
    - Manage file paths (see VideoAssetManager)
    - Compose final videos (see VideoCompositor)
    - Generate thumbnails (see ThumbnailGenerator)
    """

    def __init__(self, asset_manager: "VideoAssetManager") -> None:
        """Initialize renderer with asset manager for path access.

        Args:
            asset_manager: VideoAssetManager instance providing template and resource paths
        """
        self._asset_manager = asset_manager

    def overlay_texts_template(self, video_file_clip: VideoFileClip, video: Video) -> list[TextClip]:
        """Generate horizontal format text overlays (6 TextClips + 1 ImageClip).

        Creates text overlays for score, title, channel, views, and QR code
        positioned for horizontal video format (1920x1080).

        Args:
            video_file_clip: Source video clip for duration reference
            video: Video metadata (score, title, channel, etc.)

        Returns:
            List of 7 clips: 6 TextClip instances + 1 ImageClip (QR code)
        """
        map_score_growth = {
            VideoScoreStatus.NEW: "~",
            VideoScoreStatus.UP: "5",
            VideoScoreStatus.DOWN: "6",
            VideoScoreStatus.EQUAL: ";",
        }
        map_score_growth_color = {
            VideoScoreStatus.NEW: "yellow",
            VideoScoreStatus.UP: "blue",
            VideoScoreStatus.DOWN: "red",
            VideoScoreStatus.EQUAL: "white",
        }

        map_view_growth_color = {
            VideoScoreStatus.NEW: "black",
            VideoScoreStatus.UP: "blue",
            VideoScoreStatus.DOWN: "red",
            VideoScoreStatus.EQUAL: "black",
        }

        score_status = video.score_status or VideoScoreStatus.NEW
        score_growth_status_value = map_score_growth[score_status]
        score_growth_status_color = map_score_growth_color[score_status]
        view_growth_color = map_view_growth_color[score_status]
        channel_name = video.channel.name if video.channel else "Unknown channel"

        max_length = 42
        video_title = video.title or ""
        title = (
            video_title.replace("(Video)", "")
            .replace("(Music Video)", "")
            .replace("Official Video", "")
            .replace("#Video", "")
            .replace("Full Video", "")
            .replace("(video)", "")
            .replace(" - ", " ")
            .replace("()", "")
            .strip()
        )[:max_length]

        views = millify(video.views, precision=2, drop_nulls=False)
        views_growth = millify(video.views_growth, precision=2, drop_nulls=False)

        # Generate QR code if not exists
        qr_path = pathlib.Path(f"{self._asset_manager.video_yt_resources_folder}/{video.video_id}_qr.png")
        if not qr_path.exists():
            qr_video = segno.make(video.yt_video_url)
            qr_video.save(str(qr_path), dark="pink", light="#323524", scale=8)

        # Font path resolution with fallbacks
        font_droid_sans_path = "/usr/share/fonts/droidsans.ttf"
        font_webdings_path = "/usr/share/fonts/webdings.ttf"
        font_monocraft_path = "/usr/share/fonts/monocraft.otf"

        font_droid_sans = font_droid_sans_path if pathlib.Path(font_droid_sans_path).exists() else "DejaVu Sans Mono"
        font_webdings = font_webdings_path if pathlib.Path(font_webdings_path).exists() else "Liberation Sans"
        font_monocraft = font_monocraft_path if pathlib.Path(font_monocraft_path).exists() else "DejaVu Sans Mono"

        score_text_clip = (
            TextClip(
                f"{video.score:02d}",
                font=font_droid_sans,
                fontsize=130,
                color="white",
                stroke_color="white",
                stroke_width=1,
            )
            .set_position((190, 705))
            .set_duration(video_file_clip.duration)
            .set_start(0)
        )
        score_growth_status_text_clip = (
            TextClip(
                score_growth_status_value,
                font=font_webdings,
                fontsize=77,
                color=score_growth_status_color,
                stroke_color="white",
                stroke_width=4,
            )
            .set_position((335, 730))
            .set_duration(video_file_clip.duration)
            .set_start(0)
        )
        title_text_clip = (
            TextClip(
                title,
                font=font_monocraft,
                color="white",
                fontsize=42,
                kerning=-2,
                size=(1250, 120),
                align="West",
                method="caption",
            )
            .set_position((180, 940))
            .set_duration(video_file_clip.duration)
            .set_start(0)
        )
        channel_text_clip = (
            TextClip(
                f"© {channel_name}",
                font=font_monocraft,
                fontsize=24,
                color="white",
            )
            .set_position((258, 115))
            .set_duration(video_file_clip.duration)
            .set_start(0)
        )

        views_text_clip = (
            TextClip(
                f"{views}",
                font=font_monocraft,
                fontsize=41,
                color="black",
                kerning=0,
                size=(240, 80),
                align="center",
                method="caption",
            )
            .set_position((1525, 210))
            .set_duration(video_file_clip.duration)
            .set_start(0)
        )

        views_growth_text_clip = (
            TextClip(
                f"{views_growth}",
                font=font_monocraft,
                fontsize=38,
                color=view_growth_color,
                kerning=0,
                size=(240, 80),
                align="center",
                method="caption",
            )
            .set_position((1525, 480))
            .set_duration(video_file_clip.duration)
            .set_start(0)
        )

        qr_image_clip = (
            ImageClip(str(qr_path), ismask=False).set_position((1498, 688)).set_duration(video_file_clip.duration)
        )

        return [
            score_text_clip,
            score_growth_status_text_clip,
            title_text_clip,
            channel_text_clip,
            views_text_clip,
            views_growth_text_clip,
            qr_image_clip,
        ]

    def overlay_texts_vertical_template(self, video_file_clip: VideoFileClip, video: Video) -> list[TextClip]:
        """Generate vertical format text overlays (9 TextClips).

        Creates text overlays positioned for vertical video format (1080x1920).
        Includes additional clips for views/growth titles and previous score.

        Args:
            video_file_clip: Source video clip for duration reference
            video: Video metadata (score, title, channel, etc.)

        Returns:
            List of 9 TextClip instances
        """
        map_score_growth = {
            VideoScoreStatus.NEW: "~",
            VideoScoreStatus.UP: "5",
            VideoScoreStatus.DOWN: "6",
            VideoScoreStatus.EQUAL: ";",
        }
        map_score_growth_color = {
            VideoScoreStatus.NEW: "yellow",
            VideoScoreStatus.UP: "rgb( 0, 0, 205)",  # blue
            VideoScoreStatus.DOWN: "red",
            VideoScoreStatus.EQUAL: "white",
        }

        map_view_growth_color = {
            VideoScoreStatus.NEW: "black",
            VideoScoreStatus.UP: "rgb( 0, 0, 205)",  # blue
            VideoScoreStatus.DOWN: "red",
            VideoScoreStatus.EQUAL: "black",
        }

        score_status = video.score_status or VideoScoreStatus.NEW
        score_growth_status_value = map_score_growth[score_status]
        score_growth_status_color = map_score_growth_color[score_status]
        view_growth_color = map_view_growth_color[score_status]
        channel_name = video.channel.name if video.channel else "Unknown channel"

        max_length = 38
        title = video.yt_video_title_cleaned[:max_length]

        views = millify(video.views, precision=2, drop_nulls=False)
        views_growth = millify(video.views_growth, precision=2, drop_nulls=False)

        # Font path resolution with fallbacks
        font_droid_sans_path = "/usr/share/fonts/droidsans.ttf"
        font_webdings_path = "/usr/share/fonts/webdings.ttf"
        font_monocraft_path = "/usr/share/fonts/monocraft.otf"

        font_droid_sans = font_droid_sans_path if pathlib.Path(font_droid_sans_path).exists() else "DejaVu Sans Mono"
        font_webdings = font_webdings_path if pathlib.Path(font_webdings_path).exists() else "Liberation Sans"
        font_monocraft = font_monocraft_path if pathlib.Path(font_monocraft_path).exists() else "DejaVu Sans Mono"

        score_text_clip = (
            TextClip(
                f"{video.score:02d}",
                font=font_droid_sans,
                fontsize=240,
                color="white",
                stroke_color="white",
                stroke_width=1,
            )
            .set_position((96, 770))
            .set_duration(video_file_clip.duration)
            .set_start(0)
        )
        score_growth_status_text_clip = (
            TextClip(
                score_growth_status_value,
                font=font_webdings,
                fontsize=77,
                color=score_growth_status_color,
                stroke_color="white",
                stroke_width=4,
            )
            .set_position((170, 990))
            .set_duration(video_file_clip.duration)
            .set_start(0)
        )
        score_previous_text_clip = (
            TextClip(
                f"{video.score_previous or 'N'}",
                font=font_droid_sans,
                fontsize=66,
                color=score_growth_status_color,
            )
            .set_position((245, 995))
            .set_duration(video_file_clip.duration)
            .set_start(0)
        )
        title_text_clip = (
            TextClip(
                title,
                font=font_monocraft,
                color="white",
                fontsize=58,
                kerning=-2,
                size=(850, 180),
                align="West",
                method="caption",
            )
            .set_position((83, 1180))
            .set_duration(video_file_clip.duration)
            .set_start(0)
        )
        channel_text_clip = (
            TextClip(
                f"© {channel_name}",
                font=font_monocraft,
                fontsize=24,
                color="white",
            )
            .set_position((83, 1347))
            .set_duration(video_file_clip.duration)
            .set_start(0)
        )

        views_text_clip = (
            TextClip(
                f"{views}",
                font=font_monocraft,
                fontsize=58,
                color="white",
                kerning=0,
                size=(300, 200),
                align="center",
                method="caption",
            )
            .set_position((83, 1400))
            .set_duration(video_file_clip.duration)
            .set_start(0)
        )

        views_title_text_clip = (
            TextClip(
                "views",
                font=font_monocraft,
                fontsize=24,
                color="white",
                kerning=0,
                size=(190, 131),
                align="center",
                method="caption",
            )
            .set_position((83, 1400 + 80))
            .set_duration(video_file_clip.duration)
            .set_start(0)
        )

        views_growth_text_clip = (
            TextClip(
                f"{views_growth}",
                font=font_monocraft,
                fontsize=58,
                color=view_growth_color,
                kerning=0,
                size=(300, 200),
                align="center",
                method="caption",
            )
            .set_position((400, 1400))
            .set_duration(video_file_clip.duration)
            .set_start(0)
        )

        views_growth_title_text_clip = (
            TextClip(
                "NEW views",
                font=font_monocraft,
                fontsize=24,
                color=view_growth_color,
                kerning=0,
                size=(190, 131),
                align="center",
                method="caption",
            )
            .set_position((480, 1400 + 80))
            .set_duration(video_file_clip.duration)
            .set_start(0)
        )

        return [
            score_text_clip,
            score_growth_status_text_clip,
            score_previous_text_clip,
            title_text_clip,
            channel_text_clip,
            views_text_clip,
            views_title_text_clip,
            views_growth_text_clip,
            views_growth_title_text_clip,
        ]

    async def overlay_with_video_template(self, video_file_clip: VideoFileClip) -> list[MoviePyClip]:
        """Apply horizontal template overlay with blue screen masking.

        Creates a 3-layer composition: black base, original video, masked template.
        Template blue screen [0,0,255] is removed with color masking.

        Args:
            video_file_clip: Source video clip to overlay template on

        Returns:
            List of 3 clips: [base_clip, video_file_clip, masked_template_clip]
        """
        overlay_clip = VideoFileClip(
            filename=self._asset_manager.template_file,
            target_resolution=(video_file_clip.h, video_file_clip.w),
        ).set_duration(video_file_clip.duration)
        masked_clip = overlay_clip.fx(mask_color, color=[0, 0, 255], thr=40, s=3).set_duration(video_file_clip.duration)

        base_clip = ColorClip(
            size=(video_file_clip.w, video_file_clip.h),
            color=(0, 0, 0),
            duration=video_file_clip.duration,
        )
        return [
            base_clip,
            video_file_clip,
            masked_clip,
        ]

    async def overlay_with_vertical_video_template(self, video_file_clip: VideoFileClip) -> list[MoviePyClip]:
        """Apply vertical template overlay with crop/resize transformations.

        Creates a 3-layer composition for vertical format (1080x1920).
        Video is cropped (x1=15), resized to 1080/1.3 x 1920/1.3, and repositioned.

        Args:
            video_file_clip: Source video clip to overlay template on

        Returns:
            List of 3 clips: [base_clip, transformed_video, masked_template_clip]
        """
        overlay_clip = VideoFileClip(
            filename=self._asset_manager.template_vertical_file,
            target_resolution=(1920, 1080),
        ).set_duration(video_file_clip.duration)
        masked_clip = overlay_clip.fx(mask_color, color=[0, 0, 255], thr=50, s=3).set_duration(video_file_clip.duration)

        clip2 = (
            video_file_clip.fx(crop, x1=15)
            .fx(resize, width=1080 / 1.3, height=1920 / 1.3)
            .set_pos("top")
            .set_position((-500, -150))
        )

        base_clip = ColorClip(
            size=(1080, 1920),
            color=(0, 0, 0),
            duration=video_file_clip.duration,
        )
        return [
            base_clip,
            clip2,
            masked_clip,
        ]
