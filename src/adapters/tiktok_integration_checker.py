from __future__ import annotations

from src.config.settings import get_app_settings
from src.domain.models import IntegrationCheckResult, IntegrationCheckStatus, IntegrationPlatform
from src.infrastructure.social.tiktok_uploader_client import (
    TikTokUploaderClient,
    is_tiktok_uploader_available,
)


class TikTokIntegrationChecker:
    @property
    def platform_name(self) -> IntegrationPlatform:
        return IntegrationPlatform.TIKTOK

    @property
    def is_configured(self) -> bool:
        settings = get_app_settings()
        return is_tiktok_uploader_available() and bool(settings.tiktok_cookies_file or settings.tiktok_user_openid)

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
                message="Missing TikTok uploader dependency or cookies configuration.",
            )

        try:
            client = TikTokUploaderClient()
            is_available = client.check_connection()
            if is_available:
                return IntegrationCheckResult(
                    platform=self.platform_name,
                    status=IntegrationCheckStatus.OK,
                    is_configured=True,
                    is_publish_target=self.is_publish_target,
                    message="TikTok uploader dependency and cookies are ready.",
                )
            return IntegrationCheckResult(
                platform=self.platform_name,
                status=IntegrationCheckStatus.ERROR,
                is_configured=True,
                is_publish_target=self.is_publish_target,
                message="TikTok uploader initialization failed.",
            )
        except Exception as exc:  # noqa: BLE001
            return IntegrationCheckResult(
                platform=self.platform_name,
                status=IntegrationCheckStatus.ERROR,
                is_configured=True,
                is_publish_target=self.is_publish_target,
                message=str(exc),
            )
