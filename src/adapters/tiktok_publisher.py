from src.config.settings import get_app_settings
from src.domain.models import CanonicalVideo, Platform, PublishingResult
from src.tiktok_client import TikTokClient


class TikTokPublisher:
    @property
    def platform_name(self) -> Platform:
        return Platform.TIKTOK

    @property
    def is_enabled(self) -> bool:
        return bool(get_app_settings().tiktok_user_openid)

    async def publish_video(
        self, video_list: list[CanonicalVideo], file_path: str, title: str, description: str
    ) -> PublishingResult:
        try:
            client = TikTokClient()
            published_id = await client.upload_video(file_path, title)
            return PublishingResult(platform=self.platform_name, success=True, published_id=published_id)
        except Exception as exc:
            return PublishingResult(platform=self.platform_name, success=False, error=str(exc))
