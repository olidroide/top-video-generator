"""ThumbnailGenerator — 2x2 grid thumbnail generation from 4 video thumbnails.

C1.3 extraction: Generates a composite thumbnail by downloading 4 video thumbnails,
resizing them to fit a 2x2 grid, and overlaying date text.
"""

import datetime

import requests
from PIL import Image, ImageDraw, ImageFont

from src.domain.models import Video

from .asset_manager import VideoAssetManager


class ThumbnailGenerator:
    """Generates 2x2 grid thumbnails from 4 Video objects.

    Dependencies:
        - VideoAssetManager: provides template_file, thumbnail_font_file, video_generated_folder paths
        - PIL (Image, ImageDraw, ImageFont): for image manipulation
        - requests: for downloading video thumbnails from URLs
    """

    def __init__(self, asset_manager: VideoAssetManager) -> None:
        """Initialize with VideoAssetManager for path resolution.

        Args:
            asset_manager: VideoAssetManager instance providing resource paths.
        """
        self._asset_manager = asset_manager
        self._thumbnail_file = asset_manager.template_file
        self._thumbnail_font_file = asset_manager.thumbnail_font_file
        self._video_generated_folder = asset_manager.video_generated_folder

    async def generate_thumbnail(self, video_list: list[Video]) -> str:
        """Generate 2x2 grid thumbnail from 4 video thumbnails.

        Sorts videos by score, downloads YouTube thumbnails, resizes to quadrants,
        overlays date text, and saves as JPEG.

        Args:
            video_list: List of Video objects (expected 4 videos for 2x2 grid).

        Returns:
            Path to generated thumbnail JPEG file.
        """
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

        text_date = datetime.datetime.now(datetime.UTC).strftime("%d / %m / %Y")
        draw_surface.text((996, 960), text_date, font=title_font, fill=(0, 0, 0, 0))

        text_date_file = datetime.datetime.now(datetime.UTC).strftime("%Y%m%d")
        path = f"{self._video_generated_folder}/{text_date_file}_thumbnail.jpg"
        canvas.save(path, quality=100, optimize=True)
        return path
