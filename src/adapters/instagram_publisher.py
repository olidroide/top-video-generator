from collections.abc import Sequence

from src.config.settings import get_app_settings
from src.domain.models import CanonicalVideo, Platform, PublishingResult
from src.infrastructure.social.instagram_client import InstagramClient, is_instagrapi_available


class InstagramPublisher:
    @property
    def platform_name(self) -> Platform:
        return Platform.INSTAGRAM

    @property
    def is_enabled(self) -> bool:
        return bool(get_app_settings().instagram_client_username) and is_instagrapi_available()

    async def publish_video(
        self, video_list: Sequence[CanonicalVideo], file_path: str, title: str, description: str
    ) -> PublishingResult:
        _ = video_list, description
        try:
            client = InstagramClient()
            published_id = await client.upload_video(file_path, title)
            if not published_id:
                return PublishingResult(
                    platform=self.platform_name,
                    success=False,
                    error="instagram upload returned no media id",
                )
            return PublishingResult(platform=self.platform_name, success=True, published_id=published_id)
        except Exception as exc:  # noqa: BLE001
            return PublishingResult(platform=self.platform_name, success=False, error=str(exc))
