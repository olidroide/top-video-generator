import datetime
import pathlib
import shutil
from datetime import timezone

import requests
import segno as segno
from millify import millify
from moviepy import Clip
from moviepy.audio.fx.audio_fadeout import audio_fadeout
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from moviepy.video.compositing.transitions import crossfadein
from moviepy.video.fx.crop import crop
from moviepy.video.fx.mask_color import mask_color
from moviepy.video.fx.resize import resize
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.VideoClip import ColorClip, ImageClip, TextClip
from PIL import Image, ImageDraw, ImageFont

from src.db_client import Video, VideoScoreStatus
from src.logger import get_logger
from src.settings import get_app_settings
from src.video_downloader import VideoDownloader

logger = get_logger(__name__)


class VideoProcessing:
    def __init__(self) -> None:
        super().__init__()
        settings = get_app_settings()
        self._end_screen_file = settings.video_template_end_screen_file
        self._start_screen_file = settings.video_template_start_screen_file
        self._template_file = settings.video_template_file
        self._template_vertical_file = settings.video_template_vertical_file
        self._thumbnail_file = settings.video_template_thumbnail_file
        self._thumbnail_font_file = settings.video_template_thumbnail_font_file
        self._video_yt_resources_folder = VideoDownloader().video_yt_resources_folder
        path = pathlib.Path(
            f"{settings.video_generated_folder}/{datetime.datetime.now(timezone.utc).strftime('%Y%m%d')}/"
        )
        path.mkdir(parents=True, exist_ok=True)
        self._video_generated_folder = str(path)

    def _overlay_texts_template(self, video_file_clip: VideoFileClip, video: Video) -> list[TextClip]:
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

        score_growth_status_value = map_score_growth.get(video.score_status, "~")
        score_growth_status_color = map_score_growth_color.get(video.score_status, "white")
        view_growth_color = map_view_growth_color.get(video.score_status, "black")

        max_length = 42
        title = (
            video.title.replace("(Video)", "")
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

        if not pathlib.Path(f"{self._video_yt_resources_folder}/{video.video_id}_qr.png").exists():
            qr_video = segno.make(video.yt_video_url)
            qr_video.save(
                f"{self._video_yt_resources_folder}/{video.video_id}_qr.png", dark="pink", light="#323524", scale=8
            )

        font_droid_sans = "Droid Sans Mono"
        font_webdings = "Webdings"
        font_monocraft = "Monocraft"
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
                f"© {video.channel.name}",
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
            ImageClip(f"{self._video_yt_resources_folder}/{video.video_id}_qr.png", ismask=False)
            .set_position((1498, 688))
            .set_duration(video_file_clip.duration)
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

    def _overlay_texts_vertical_template(self, video_file_clip: VideoFileClip, video: Video) -> list[TextClip]:
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

        score_growth_status_value = map_score_growth.get(video.score_status, "~")
        score_growth_status_color = map_score_growth_color.get(video.score_status, "white")
        view_growth_color = map_view_growth_color.get(video.score_status, "black")

        max_length = 38
        title = video.yt_video_title_cleaned[:max_length]

        views = millify(video.views, precision=2, drop_nulls=False)
        views_growth = millify(video.views_growth, precision=2, drop_nulls=False)

        font_droid_sans = "Droid Sans Mono"
        font_webdings = "Webdings"
        font_monocraft = "Monocraft"
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
                # stroke_color="white",
                # stroke_width=1,
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
                f"© {video.channel.name}",
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

    async def _overlay_with_video_template(self, video_file_clip: VideoFileClip) -> list[Clip]:
        overlay_clip = VideoFileClip(
            filename=self._template_file,
            target_resolution=(video_file_clip.h, video_file_clip.w),
        ).set_duration(video_file_clip.duration)
        masked_clip = overlay_clip.fx(mask_color, color=[0, 0, 255], thr=40, s=3).set_duration(video_file_clip.duration)

        # clip2 = clip.fx(resize, height=560, width=760).fx(mask_and, overlay_clip).set_pos(('center'))
        # clip2 = clip.fx(mask_and, masked_clip).set_pos(("center"))
        # clip2.set_position("center")

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

    async def _overlay_with_vertical_video_template(self, video_file_clip: VideoFileClip) -> list[Clip]:
        overlay_clip = VideoFileClip(
            filename=self._template_vertical_file,
            target_resolution=(1920, 1080),
        ).set_duration(video_file_clip.duration)
        masked_clip = overlay_clip.fx(mask_color, color=[0, 0, 255], thr=50, s=3).set_duration(video_file_clip.duration)

        clip2 = (
            video_file_clip.fx(crop, x1=15)
            .fx(resize, width=1080 / 1.3, height=1920 / 1.3)
            .set_pos("top")
            .set_position((-500, -150))
        )
        # clip2 = clip.fx(mask_and, masked_clip).set_pos(("center"))

        # video_file_clip.set_position("center")

        base_clip = ColorClip(
            size=(1080, 1920),
            color=(0, 0, 0),
            duration=video_file_clip.duration,
        )
        return [
            base_clip,
            clip2,
            # video_file_clip,
            masked_clip,
        ]

    async def post_process_video(self, video: Video):
        logger.debug("start post_process_video", video=video.video_id)
        x_width = 1920
        y_height = 1080
        seconds_per_clip = 8
        clip = VideoFileClip(
            filename=f"{self._video_yt_resources_folder}/{video.video_id}.mp4",
            target_resolution=(y_height, x_width),
        )
        if clip.duration < 50:
            clip = clip.subclip(t_start=0, t_end=seconds_per_clip)
        else:
            start = int(clip.duration / 2)
            clip = clip.subclip(t_start=start, t_end=start + seconds_per_clip)

        clips = list(await self._overlay_with_video_template(video_file_clip=clip))
        clips.extend(self._overlay_texts_template(video_file_clip=clip, video=video))

        composite_video_clip = CompositeVideoClip(clips=clips)

        await self._render_clip(composite_video_clip, video.video_id)
        logger.debug("finish post_process_video", video=video.video_id)

    async def post_process_vertical_video(self, video: Video):
        logger.debug(f"start {self.post_process_vertical_video.__name__}", video=video.video_id)
        _x_width = 1080
        _y_height = 1920
        seconds_per_clip = 8
        clip = VideoFileClip(
            filename=f"{self._video_yt_resources_folder}/{video.video_id}.mp4",
            # target_resolution=(y_height, x_width),
        )
        clip = clip.set_position("top")
        if clip.duration < 50:
            clip = clip.subclip(t_start=0, t_end=seconds_per_clip)
        else:
            start = int(clip.duration / 2)
            clip = clip.subclip(t_start=start, t_end=start + seconds_per_clip)

        clips = list(await self._overlay_with_vertical_video_template(video_file_clip=clip))
        clips.extend(self._overlay_texts_vertical_template(video_file_clip=clip, video=video))

        composite_video_clip = CompositeVideoClip(clips=clips)

        await self._render_clip(composite_video_clip, f"{video.video_id}_vertical")

        logger.debug("finish post_process_vertical_video", video=video.video_id)

    async def join_processed_videos(self, video_id_list: list[str], vertical: bool = False) -> str:
        cross_fade_duration = 1
        if not vertical:
            composite_clips = [
                VideoFileClip(self._start_screen_file).fx(audio_fadeout, cross_fade_duration),
            ]
        else:
            video_id = video_id_list.pop(0)
            file_path = f"{self._video_generated_folder}/{video_id}{'_vertical' if vertical else ''}_format.mp4"
            composite_clips = [
                VideoFileClip(file_path).fx(audio_fadeout, cross_fade_duration),
            ]

        for index, video_id in enumerate(video_id_list):
            clip = VideoFileClip(
                f"{self._video_generated_folder}/{video_id}{'_vertical' if vertical else ''}_format.mp4"
            )
            composite_clips.append(
                crossfadein(
                    clip.set_start(composite_clips[index].end - cross_fade_duration).fx(
                        audio_fadeout, cross_fade_duration
                    ),
                    cross_fade_duration,
                )
            )

        if not vertical:
            clip = VideoFileClip(self._end_screen_file)
            composite_clips.append(
                crossfadein(
                    clip.set_start(composite_clips[len(composite_clips) - 1].end - cross_fade_duration).fx(
                        audio_fadeout, cross_fade_duration
                    ),
                    cross_fade_duration,
                )
            )

        merged_clip = CompositeVideoClip(clips=composite_clips)
        return await self._render_clip(
            merged_clip, datetime.datetime.now(timezone.utc).strftime("%Y%m%d") + f"{'_vertical' if vertical else ''}"
        )

    async def generate_thumbnail(self, video_list: list[Video]):
        video_list.sort(key=lambda x: x.score)
        with Image.open(self._thumbnail_file) as base_thumbnail:
            base_thumbnail.load()

        middle_width_point = int(base_thumbnail.width / 2)
        middle_height_point = int(base_thumbnail.height / 2)
        clips_thumbnails = []
        for video in video_list:
            with Image.open(requests.get(video.yt_video_thumbnail_url, stream=True).raw) as clip_thumbnail:
                clip_thumbnail.load()
                clips_thumbnails.append(clip_thumbnail.resize(size=(middle_width_point, middle_height_point)))

        canvas = Image.new("RGB", (base_thumbnail.width, base_thumbnail.height))
        for index, clip_thumbnail in enumerate(clips_thumbnails):
            if index == 0:
                position = (0, 0)
            elif index == 1:
                position = (middle_width_point, 0)
            elif index == 2:
                position = (0, middle_height_point)
            else:
                position = (middle_width_point, middle_height_point)

            canvas.paste(clip_thumbnail, position)

        canvas.paste(base_thumbnail, (0, 0), base_thumbnail)
        title_font = ImageFont.truetype(self._thumbnail_font_file, size=70)
        draw_surface = ImageDraw.Draw(canvas, "RGBA")

        text_date = datetime.datetime.now(timezone.utc).strftime("%d / %m / %Y")
        draw_surface.text((996, 960), text_date, font=title_font, fill=(0, 0, 0, 0))

        text_date_file = datetime.datetime.now(timezone.utc).strftime("%Y%m%d")
        path = f"{self._video_generated_folder}/{text_date_file}_thumbnail.jpg"
        canvas.save(path, quality=100, optimize=True)
        return path

    async def _render_clip(self, video: CompositeVideoClip, video_id: str) -> str:
        logger.debug("start render clip", video_id=video_id)
        path = pathlib.Path(f"{self._video_generated_folder}/{video_id}_format.mp4")
        if path.exists():
            return str(path)
        if not (threads := get_app_settings().threads_workers):
            threads = 1

        video.write_videofile(
            str(path),
            remove_temp=True,
            temp_audiofile=f"/tmp/temp_{video_id}_audio.mp4",
            verbose=False,
            logger=None,
            fps=24,
            codec="libx264",  # or use newer "libx265"
            # codec="libx265",  # better compression
            threads=threads,
            preset="ultrafast",  # veryfast
            # bitrate="8M",
        )

        return str(path)

    async def delete_processed_videos(self):
        try:
            shutil.rmtree(self._video_generated_folder)
        except Exception as e:
            logger.error("Fail to delete processed videos folder", exception=e)
