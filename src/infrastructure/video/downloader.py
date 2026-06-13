"""YouTube source video downloader."""

import pathlib
from collections.abc import Callable
from typing import Any

from yt_dlp import YoutubeDL

from src.config.settings import get_app_settings
from src.domain.models import Video
from src.shared.logging import get_logger

logger = get_logger(__name__)


class VideoDownloader:
    _SHORTS_MAX_DURATION_SECONDS = 60
    _VIDEO_EXTENSIONS = (".mp4", ".webm", ".mkv", ".mov", ".m4v")

    def __init__(self) -> None:
        super().__init__()
        settings = get_app_settings()
        path = pathlib.Path(f"{settings.video_generated_folder}/yt/")
        path.mkdir(parents=True, exist_ok=True)
        self.video_yt_resources_folder = str(path)

    def _existing_video_path(self, video_id: str) -> pathlib.Path | None:
        base_folder = pathlib.Path(self.video_yt_resources_folder)
        preferred_mp4 = base_folder / f"{video_id}.mp4"
        if preferred_mp4.exists():
            return preferred_mp4

        for candidate in sorted(base_folder.glob(f"{video_id}.*")):
            if candidate.is_file() and candidate.suffix.lower() in self._VIDEO_EXTENSIONS:
                return candidate

        return None

    def is_already_downloaded(self, video: Video) -> bool:
        return self._existing_video_path(video.video_id) is not None

    def _ydl_opts(self) -> dict[str, Any]:
        return {
            "outtmpl": f"{self.video_yt_resources_folder}/%(id)s.%(ext)s",
            "format": "best[height<=720][ext=mp4]/best[height<=720]/best[ext=mp4]/best/mp4",
            "noplaylist": True,
            "quiet": True,
            "download_ranges": self._download_ranges(),
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
                "User-Agent": "com.google.ios.youtube/19.29.1 (iPhone16,2; U; CPU iOS 17_5_1 like Mac OS X);",
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

    @staticmethod
    def _download_ranges() -> Callable[[dict[str, Any], Any], list[dict[str, int]]]:
        return lambda _info_dict, _ydl: [{"start_time": 30, "end_time": 90}]

    def _classify_pending_videos(self, video_list: list[Video]) -> tuple[list[Video], list[str], list[str]]:
        pending_videos: list[Video] = []
        yt_urls: list[str] = []
        yt_shorts_urls: list[str] = []

        for video in video_list:
            if self.is_already_downloaded(video):
                continue

            duration = video.duration
            if duration is None:
                continue

            pending_videos.append(video)
            if duration > self._SHORTS_MAX_DURATION_SECONDS:
                yt_urls.append(video.yt_video_url)
            else:
                yt_shorts_urls.append(video.yt_video_url)

        return pending_videos, yt_urls, yt_shorts_urls

    def _missing_video_ids(self, pending_videos: list[Video]) -> list[str]:
        return [video.video_id for video in pending_videos if not self.is_already_downloaded(video)]

    async def download_video(self, video_list: list[Video]) -> None:
        pending_videos, yt_urls, yt_shorts_urls = self._classify_pending_videos(video_list)

        if not yt_urls and not yt_shorts_urls:
            logger.info("youtube_downloader.no_videos_to_download")
            return

        logger.debug("youtube_downloader.start", video_list=yt_urls, video_shorts=yt_shorts_urls)

        if yt_urls:
            ytdl_options = self._ydl_opts()
            with YoutubeDL(ytdl_options) as ydl:
                for url in yt_urls:
                    try:
                        logger.info("youtube_downloader.download_long", url=url)
                        ydl.download([url])
                    except Exception as exc:
                        logger.exception("youtube_downloader.download_long_failed", url=url, error=str(exc))
                        continue

        if yt_shorts_urls:
            ytdl_options = self._ydl_opts()
            ytdl_options.pop("download_ranges", None)
            with YoutubeDL(ytdl_options) as ydl:
                for url in yt_shorts_urls:
                    try:
                        logger.info("youtube_downloader.download_short", url=url)
                        ydl.download([url])
                    except Exception as exc:
                        logger.exception("youtube_downloader.download_short_failed", url=url, error=str(exc))
                        continue

        missing_video_ids = self._missing_video_ids(pending_videos)
        if missing_video_ids:
            logger.error("youtube_downloader.missing_assets", video_ids=missing_video_ids)
            raise RuntimeError(f"Missing downloaded assets for video IDs: {', '.join(missing_video_ids)}")

        logger.info("youtube_downloader.finished", long_videos=yt_urls, short_videos=yt_shorts_urls)
