from __future__ import annotations

from src.config.settings import get_app_settings
from src.domain.models import IntegrationCheckResult, IntegrationCheckStatus, IntegrationPlatform
from src.infrastructure.social.tiktok_client import TikTokClient


class TikTokIntegrationChecker:
    @property
    def platform_name(self) -> IntegrationPlatform:
        return IntegrationPlatform.TIKTOK

    @property
    def is_configured(self) -> bool:
        settings = get_app_settings()
        return bool(settings.tiktok_client_key and settings.tiktok_client_secret and settings.tiktok_user_openid)

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
                message="Missing TikTok OAuth configuration.",
            )

        try:
            client = TikTokClient()
            creator_info = await client.check_connection()
            if creator_info and not creator_info.error:
                return IntegrationCheckResult(
                    platform=self.platform_name,
                    status=IntegrationCheckStatus.OK,
                    is_configured=True,
                    is_publish_target=self.is_publish_target,
                    message="TikTok creator access verified.",
                )
            error_message = creator_info.error.message if creator_info and creator_info.error else None
            return IntegrationCheckResult(
                platform=self.platform_name,
                status=IntegrationCheckStatus.ERROR,
                is_configured=True,
                is_publish_target=self.is_publish_target,
                message=error_message or "TikTok creator check failed.",
            )
        except Exception as exc:  # noqa: BLE001
            return IntegrationCheckResult(
                platform=self.platform_name,
                status=IntegrationCheckStatus.ERROR,
                is_configured=True,
                is_publish_target=self.is_publish_target,
                message=str(exc),
            )
