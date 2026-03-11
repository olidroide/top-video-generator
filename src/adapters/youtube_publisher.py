from src.config.settings import get_app_settings
from src.domain.models import CanonicalVideo, Platform, PublishingResult
from src.infrastructure.youtube import get_yt_client


class YouTubePublisher:
    @property
    def platform_name(self) -> Platform:
        return Platform.YOUTUBE

    @property
    def is_enabled(self) -> bool:
        return bool(get_app_settings().yt_client_secret_file)

    async def publish_video(
        self, video_list: list[CanonicalVideo], file_path: str, title: str, description: str
    ) -> PublishingResult:
        try:
            client = get_yt_client()
            published_id = await client.upload_video(file_path, title, description)
            return PublishingResult(platform=self.platform_name, success=True, published_id=published_id)
        except Exception as exc:
            return PublishingResult(platform=self.platform_name, success=False, error=str(exc))
