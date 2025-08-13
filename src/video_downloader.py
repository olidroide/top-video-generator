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
            "outtmpl": f"{self.video_yt_resources_folder}/%(id)s.%(ext)s",
            "format": "best[height<=720][ext=mp4]/best[height<=720]/best[ext=mp4]/best/mp4",
            "noplaylist": True,
            "quiet": True,
            "download_ranges": lambda info_dict, ydl: [{"start_time": 30, "end_time": 90}],
            "force_keyframes_at_cuts": True,
            "noprogress": True,
            "extractor_args": {
                "youtube": {
                    "player_client": ["ios", "android", "web"],
                    "skip": ["dash", "hls"],
                    "formats": "missing_pot",
                }
            },
            "http_headers": {
                "User-Agent": "com.google.ios.youtube/19.29.1 (iPhone16,2; U; CPU iOS 17_5_1 like Mac OS X;)",
                "X-YouTube-Client-Name": "5",
                "X-YouTube-Client-Version": "19.29.1",
            },
            "ignoreerrors": True,
            "retries": 10,
            "fragment_retries": 10,
            "force_json": True,
            "cookiefile": None,
            "socket_timeout": 60,
            "source_address": None,
            "sleep_interval": 1,
            "max_sleep_interval": 5,
            "nocheckcertificate": True,
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
            logger.info("🚫 No videos to download!")
            return

        logger.debug("⬇️ Starting video downloads", video_list=yt_urls, video_shorts=yt_shorts_urls)

        if yt_urls:
            ytdl_options = self._ydl_opts()
            with YoutubeDL(ytdl_options) as ydl:
                for url in yt_urls:
                    try:
                        logger.info(f"🎬 Downloading long video: {url}")
                        ydl.download([url])
                    except Exception as e:
                        logger.error(f"❌ Error downloading long video {url}: {str(e)}")
                        continue

        if yt_shorts_urls:
            ytdl_options = self._ydl_opts()
            ytdl_options.pop("download_ranges", None)
            with YoutubeDL(ytdl_options) as ydl:
                for url in yt_shorts_urls:
                    try:
                        logger.info(f"📱 Downloading short video: {url}")
                        ydl.download([url])
                    except Exception as e:
                        logger.error(f"❌ Error downloading short video {url}: {str(e)}")
                        continue

        logger.info(f"✅ Finished downloading videos! Long: {yt_urls} | Shorts: {yt_shorts_urls}")
