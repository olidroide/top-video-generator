"""Use case to handle OAuth authorization flows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.ports import SpotifyOAuthProvider, TikTokOAuthProvider, YouTubeOAuthProvider
    from src.infrastructure.storage.auth_repository import AuthenticationRepository

from src.domain.models import SpotifyAuth, TikTokAuth, YtAuth
from src.shared.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class AuthorizeYtRequest:
    code: str
    url_requested: str


@dataclass(frozen=True)
class AuthorizeTikTokRequest:
    code: str


@dataclass(frozen=True)
class AuthorizeSpotifyRequest:
    code: str


class AuthorizeUseCase:
    """Handles OAuth authorization callbacks and persistence."""

    def __init__(
        self,
        auth_repo: AuthenticationRepository,
        yt_provider: YouTubeOAuthProvider,
        tiktok_provider: TikTokOAuthProvider,
        spotify_provider: SpotifyOAuthProvider,
    ) -> None:
        self._auth_repo = auth_repo
        self._yt_provider = yt_provider
        self._tiktok_provider = tiktok_provider
        self._spotify_provider = spotify_provider

    async def execute_yt(self, request: AuthorizeYtRequest) -> YtAuth:
        """Exchange code and save YT credentials."""
        oauth_credentials = self._yt_provider.step_2_exchange_code_authentication(
            url_requested=request.url_requested,
        )
        return self._auth_repo.add_or_update_yt_auth(
            YtAuth(
                token=oauth_credentials.get("token"),
                refresh_token=oauth_credentials.get("refresh_token"),
                token_uri=oauth_credentials.get("token_uri"),
                client_id=oauth_credentials.get("client_id"),
                client_secret=oauth_credentials.get("client_secret"),
                scopes=oauth_credentials.get("scopes"),
            )
        )

    async def execute_tiktok(self, request: AuthorizeTikTokRequest) -> TikTokAuth:
        """Exchange code and save TikTok credentials."""
        oauth_credentials = await self._tiktok_provider.step_2_exchange_code_authentication(
            user_code=request.code,
        )
        return self._auth_repo.add_or_update_tiktok_auth(
            TikTokAuth(
                token=oauth_credentials.get("access_token"),
                refresh_token=oauth_credentials.get("refresh_token"),
                client_id=oauth_credentials.get("open_id"),
                scopes=str(oauth_credentials.get("scope") or "").split(","),
            )
        )

    async def execute_spotify(self, request: AuthorizeSpotifyRequest) -> SpotifyAuth:
        """Exchange code and save Spotify credentials."""
        oauth_credentials = await self._spotify_provider.step_2_exchange_code_authentication(
            user_code=request.code,
        )
        return self._auth_repo.add_or_update_spotify_auth(
            SpotifyAuth(
                token=oauth_credentials.get("access_token"),
                refresh_token=oauth_credentials.get("refresh_token"),
                client_id=oauth_credentials.get("client_id"),
                scopes=str(oauth_credentials.get("scope") or "").split(" "),
            )
        )
