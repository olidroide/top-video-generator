from __future__ import annotations

from src.config.settings import get_app_settings
from src.domain.models import IntegrationCheckResult, IntegrationCheckStatus, IntegrationPlatform
from src.infrastructure.social.spotify_client import SpotifyClient
from src.shared.logging import get_logger

logger = get_logger(__name__)

_SPOTIFY_REAUTH_MESSAGE = "Spotify authorization is invalid or expired. Reconnect Spotify from Setup."
_SPOTIFY_REAUTH_HINTS = (
    "token expired",
    "token invalid",
    "refresh_token",
    "invalid_grant",
    "valid bearer authentication",
)


def _requires_spotify_reauth(message: str) -> bool:
    normalized = message.lower()
    return any(hint in normalized for hint in _SPOTIFY_REAUTH_HINTS)


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
        logger.info("spotify_integration_checker.check_started", configured=self.is_configured)
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
                logger.info("spotify_integration_checker.check_succeeded", spotify_user_id=user_info.get("id"))
                return IntegrationCheckResult(
                    platform=self.platform_name,
                    status=IntegrationCheckStatus.OK,
                    is_configured=True,
                    is_publish_target=self.is_publish_target,
                    message="Spotify account access verified.",
                )

            spotify_error = user_info.get("error")
            if isinstance(spotify_error, dict):
                error_message = spotify_error.get("message")
                if isinstance(error_message, str) and error_message:
                    if _requires_spotify_reauth(error_message):
                        return IntegrationCheckResult(
                            platform=self.platform_name,
                            status=IntegrationCheckStatus.ERROR,
                            is_configured=True,
                            is_publish_target=self.is_publish_target,
                            message=f"{_SPOTIFY_REAUTH_MESSAGE} ({error_message})",
                        )
                    return IntegrationCheckResult(
                        platform=self.platform_name,
                        status=IntegrationCheckStatus.ERROR,
                        is_configured=True,
                        is_publish_target=self.is_publish_target,
                        message=f"Spotify API error: {error_message}",
                    )

            return IntegrationCheckResult(
                platform=self.platform_name,
                status=IntegrationCheckStatus.ERROR,
                is_configured=True,
                is_publish_target=self.is_publish_target,
                message="Spotify user check failed.",
            )
        except Exception as exc:
            logger.exception("spotify_integration_checker.check_failed", error=str(exc))
            return IntegrationCheckResult(
                platform=self.platform_name,
                status=IntegrationCheckStatus.ERROR,
                is_configured=True,
                is_publish_target=self.is_publish_target,
                message=str(exc),
            )
