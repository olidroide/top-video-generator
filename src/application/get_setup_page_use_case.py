"""Use case for loading the auth setup page."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.models import TikTokAuth, YtAuth
    from src.domain.ports import AuthCredentialStore, OAuthProvider


@dataclass(frozen=True)
class GetSetupPageRequest:
    """Request data for the auth setup page."""

    yt_session_client_id: str | None = None
    tiktok_session_client_id: str | None = None
    yt_auth_user_id: str | None = None
    tiktok_user_openid: str | None = None


@dataclass(frozen=True)
class GetSetupPageResult:
    """Result payload consumed by the SSR setup view."""

    yt_authentication_url: str | None
    yt_credentials: YtAuth | None
    tiktok_authentication_url: str | None
    tiktok_credentials: TikTokAuth | None
    is_completed: bool


class GetSetupPageUseCase:
    """Build the setup page state from auth storage and OAuth providers."""

    def __init__(
        self,
        auth_repo: AuthCredentialStore,
        yt_provider: OAuthProvider[YtAuth],
    ) -> None:
        self._auth_repo = auth_repo
        self._yt_provider = yt_provider

    async def execute(self, request: GetSetupPageRequest) -> GetSetupPageResult:
        # Setup page shows session credentials when present, but completion requires
        # persisted credentials from configured user identifiers.
        yt_persisted_credentials = self._get_yt_credentials(request.yt_auth_user_id)
        tiktok_persisted_credentials = self._get_tiktok_credentials(request.tiktok_user_openid)

        yt_credentials = self._get_yt_credentials(request.yt_session_client_id) or yt_persisted_credentials
        tiktok_credentials = (
            self._get_tiktok_credentials(request.tiktok_session_client_id) or tiktok_persisted_credentials
        )

        yt_authentication_url = None if yt_credentials else await self._yt_provider.step_1_get_authentication_url()
        tiktok_authentication_url = None

        is_completed = bool(yt_persisted_credentials and tiktok_persisted_credentials)

        return GetSetupPageResult(
            yt_authentication_url=yt_authentication_url,
            yt_credentials=yt_credentials,
            tiktok_authentication_url=tiktok_authentication_url,
            tiktok_credentials=tiktok_credentials,
            is_completed=is_completed,
        )

    def _get_yt_credentials(self, client_id: str | None) -> YtAuth | None:
        return self._auth_repo.get_yt_auth(client_id) if client_id else None

    def _get_tiktok_credentials(self, client_id: str | None) -> TikTokAuth | None:
        return self._auth_repo.get_tiktok_auth(client_id) if client_id else None
