from collections.abc import Sequence

from src.config.settings import get_app_settings
from src.domain.models import CanonicalVideo, Platform, PublishingResult
from src.infrastructure.youtube.yt_client import YTClient
from src.infrastructure.youtube.yt_fake_client import YTClientFake


def _build_yt_client() -> YTClient:
    settings = get_app_settings()
    return YTClient() if settings.is_production_env else YTClientFake()


class YouTubePublisher:
    @property
    def platform_name(self) -> Platform:
        return Platform.YOUTUBE

    @property
    def is_enabled(self) -> bool:
        return bool(get_app_settings().yt_client_secret_file)

    async def publish_video(
        self, video_list: Sequence[CanonicalVideo], file_path: str, title: str, description: str
    ) -> PublishingResult:
        _ = video_list
        try:
            client = _build_yt_client()
            published_id = await client.upload_video(file_path, title, description)
            if not published_id:
                return PublishingResult(
                    platform=self.platform_name,
                    success=False,
                    error="youtube upload returned no media id",
                )
            return PublishingResult(platform=self.platform_name, success=True, published_id=published_id)
        except Exception as exc:  # noqa: BLE001
            return PublishingResult(platform=self.platform_name, success=False, error=str(exc))
