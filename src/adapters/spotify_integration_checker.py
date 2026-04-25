from __future__ import annotations

from src.config.settings import get_app_settings
from src.domain.models import IntegrationCheckResult, IntegrationCheckStatus, IntegrationPlatform
from src.infrastructure.social.spotify_client import SpotifyClient


class SpotifyIntegrationChecker:
    @property
    def platform_name(self) -> IntegrationPlatform:
        return IntegrationPlatform.SPOTIFY

    @property
    def is_configured(self) -> bool:
        return get_app_settings().is_spotify_configured

    @property
    def is_publish_target(self) -> bool:
        return False

    async def check_connection(self) -> IntegrationCheckResult:
        if not self.is_configured:
            return IntegrationCheckResult(
                platform=self.platform_name,
                status=IntegrationCheckStatus.NOT_CONFIGURED,
                is_configured=False,
                is_publish_target=self.is_publish_target,
                message="Missing Spotify OAuth configuration.",
            )

        try:
            client = SpotifyClient()
            user_info = await client.check_connection()
            if user_info.get("id"):
                return IntegrationCheckResult(
                    platform=self.platform_name,
                    status=IntegrationCheckStatus.OK,
                    is_configured=True,
                    is_publish_target=self.is_publish_target,
                    message="Spotify account access verified.",
                )
            return IntegrationCheckResult(
                platform=self.platform_name,
                status=IntegrationCheckStatus.ERROR,
                is_configured=True,
                is_publish_target=self.is_publish_target,
                message="Spotify user check failed.",
            )
        except Exception as exc:  # noqa: BLE001
            return IntegrationCheckResult(
                platform=self.platform_name,
                status=IntegrationCheckStatus.ERROR,
                is_configured=True,
                is_publish_target=self.is_publish_target,
                message=str(exc),
            )
