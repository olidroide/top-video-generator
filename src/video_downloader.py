import pathlib

from yt_dlp import YoutubeDL

from src.db_client import Video
from src.logger import get_logger
from src.settings import get_app_settings

logger = get_logger(__name__)


class VideoDownloader:
    def __init__(self) -> None:
        super().__init__()
        settings = get_app_settings()
        path = pathlib.Path(f"{settings.video_generated_folder}/yt/")
        path.mkdir(parents=True, exist_ok=True)
        self.video_yt_resources_folder = str(path)

    def is_already_downloaded(self, video: Video) -> bool:
        return pathlib.Path(f"{self.video_yt_resources_folder}/{video.video_id}.mp4").exists()

    def _ydl_opts(self):
        return {
            "outtmpl": f"{self.video_yt_resources_folder}/%(id)s",
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best/bestvideo+bestaudio/best",
            "noplaylist": True,
            "quiet": True,
            "postprocessor_args": ["-ss", "00:00:30.00", "-to", "00:01:30.00"],
            "force_keyframes_at_cuts": True,
            "noprogress": True,
        }

    async def download_video(self, video_list: list[Video]):
        yt_urls = [
            video.yt_video_url
            for video in video_list
            if not self.is_already_downloaded(video) and (video.duration is not None and video.duration > 60)
        ]
        yt_shorts_urls = [
            video.yt_video_url
            for video in video_list
            if not self.is_already_downloaded(video) and (video.duration is not None and video.duration <= 60)
        ]
        if not yt_urls and not yt_shorts_urls:
            logger.info("no videos to download")
            return

        logger.debug("download videos", video_list=yt_urls, video_shorts=yt_shorts_urls)
        ytdl_options = self._ydl_opts()
        with YoutubeDL(ytdl_options) as ydl:
            ydl.download(yt_urls)

        ytdl_options.pop("postprocessor_args")
        with YoutubeDL(ytdl_options) as ydl:
            ydl.download(yt_shorts_urls)

        logger.info("Finish to download videos", yt_urls=yt_urls, yt_short_urls=yt_shorts_urls)
