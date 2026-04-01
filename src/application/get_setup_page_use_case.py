"""Use case for loading the auth setup page."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.models import SpotifyAuth, TikTokAuth, YtAuth
    from src.domain.ports import AuthCredentialStore, OAuthProvider


@dataclass(frozen=True)
class GetSetupPageRequest:
    """Request data for the auth setup page."""

    yt_session_client_id: str | None = None
    tiktok_session_client_id: str | None = None
    spotify_session_client_id: str | None = None
    yt_auth_user_id: str | None = None
    tiktok_user_openid: str | None = None
    spotify_user_id: str | None = None


@dataclass(frozen=True)
class GetSetupPageResult:
    """Result payload consumed by the SSR setup view."""

    yt_authentication_url: str | None
    yt_credentials: YtAuth | None
    tiktok_authentication_url: str | None
    tiktok_credentials: TikTokAuth | None
    spotify_authentication_url: str | None
    spotify_credentials: SpotifyAuth | None
    is_completed: bool


class GetSetupPageUseCase:
    """Build the setup page state from auth storage and OAuth providers."""

    def __init__(
        self,
        auth_repo: AuthCredentialStore,
        yt_provider: OAuthProvider[YtAuth],
        tiktok_provider: OAuthProvider[TikTokAuth],
        spotify_provider: OAuthProvider[SpotifyAuth],
    ) -> None:
        self._auth_repo = auth_repo
        self._yt_provider = yt_provider
        self._tiktok_provider = tiktok_provider
        self._spotify_provider = spotify_provider

    async def execute(self, request: GetSetupPageRequest) -> GetSetupPageResult:
        if self._is_completed(request):
            return GetSetupPageResult(
                yt_authentication_url=None,
                yt_credentials=self._get_yt_credentials(request.yt_session_client_id),
                tiktok_authentication_url=None,
                tiktok_credentials=self._get_tiktok_credentials(request.tiktok_session_client_id),
                spotify_authentication_url=None,
                spotify_credentials=self._get_spotify_credentials(request.spotify_session_client_id),
                is_completed=True,
            )

        yt_credentials = self._get_yt_credentials(request.yt_session_client_id)
        tiktok_credentials = self._get_tiktok_credentials(request.tiktok_session_client_id)
        spotify_credentials = self._get_spotify_credentials(request.spotify_session_client_id)

        yt_authentication_url = None if yt_credentials else await self._yt_provider.step_1_get_authentication_url()
        tiktok_authentication_url = (
            None if tiktok_credentials else await self._tiktok_provider.step_1_get_authentication_url()
        )
        spotify_authentication_url = (
            None if spotify_credentials else await self._spotify_provider.step_1_get_authentication_url()
        )

        return GetSetupPageResult(
            yt_authentication_url=yt_authentication_url,
            yt_credentials=yt_credentials,
            tiktok_authentication_url=tiktok_authentication_url,
            tiktok_credentials=tiktok_credentials,
            spotify_authentication_url=spotify_authentication_url,
            spotify_credentials=spotify_credentials,
            is_completed=False,
        )

    def _is_completed(self, request: GetSetupPageRequest) -> bool:
        if not (request.yt_auth_user_id and request.tiktok_user_openid and request.spotify_user_id):
            return False

        return bool(
            self._auth_repo.get_yt_auth(request.yt_auth_user_id)
            and self._auth_repo.get_tiktok_auth(request.tiktok_user_openid)
            and self._auth_repo.get_spotify_auth(request.spotify_user_id)
        )

    def _get_yt_credentials(self, client_id: str | None) -> YtAuth | None:
        return self._auth_repo.get_yt_auth(client_id) if client_id else None

    def _get_tiktok_credentials(self, client_id: str | None) -> TikTokAuth | None:
        return self._auth_repo.get_tiktok_auth(client_id) if client_id else None

    def _get_spotify_credentials(self, client_id: str | None) -> SpotifyAuth | None:
        return self._auth_repo.get_spotify_auth(client_id) if client_id else None
