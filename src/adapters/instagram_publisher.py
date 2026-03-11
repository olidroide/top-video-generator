from src.config.settings import get_app_settings
from src.domain.models import CanonicalVideo, Platform, PublishingResult
from src.infrastructure.social.instagram_client import InstagramClient


class InstagramPublisher:
    @property
    def platform_name(self) -> Platform:
        return Platform.INSTAGRAM

    @property
    def is_enabled(self) -> bool:
        return bool(get_app_settings().instagram_client_username)

    async def publish_video(
        self, video_list: list[CanonicalVideo], file_path: str, title: str, description: str
    ) -> PublishingResult:
        try:
            client = InstagramClient()
            published_id = await client.upload_video(file_path, title)
            return PublishingResult(platform=self.platform_name, success=True, published_id=published_id)
        except Exception as exc:
            return PublishingResult(platform=self.platform_name, success=False, error=str(exc))
