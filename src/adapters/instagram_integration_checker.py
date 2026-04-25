from __future__ import annotations

from src.config.settings import get_app_settings
from src.domain.models import IntegrationCheckResult, IntegrationCheckStatus, IntegrationPlatform
from src.infrastructure.social.instagram_client import InstagramClient, is_instagrapi_available


class InstagramIntegrationChecker:
    @property
    def platform_name(self) -> IntegrationPlatform:
        return IntegrationPlatform.INSTAGRAM

    @property
    def is_configured(self) -> bool:
        return get_app_settings().is_instagram_configured and is_instagrapi_available()

    @property
    def is_publish_target(self) -> bool:
        return True

    async def check_connection(self) -> IntegrationCheckResult:
        if not self.is_configured:
            return IntegrationCheckResult(
                platform=self.platform_name,
                status=IntegrationCheckStatus.NOT_CONFIGURED,
                is_configured=False,
                is_publish_target=self.is_publish_target,
                message="Missing Instagram credentials or dependency.",
            )

        try:
            client = InstagramClient()
            is_available = await client.check_connection()
            if is_available:
                return IntegrationCheckResult(
                    platform=self.platform_name,
                    status=IntegrationCheckStatus.OK,
                    is_configured=True,
                    is_publish_target=self.is_publish_target,
                    message="Instagram session verified.",
                )
            return IntegrationCheckResult(
                platform=self.platform_name,
                status=IntegrationCheckStatus.ERROR,
                is_configured=True,
                is_publish_target=self.is_publish_target,
                message="Instagram session check failed.",
            )
        except Exception as exc:  # noqa: BLE001
            return IntegrationCheckResult(
                platform=self.platform_name,
                status=IntegrationCheckStatus.ERROR,
                is_configured=True,
                is_publish_target=self.is_publish_target,
                message=str(exc),
            )
