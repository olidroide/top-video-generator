"""Use case to handle OAuth authorization flows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.domain.models import TikTokAuth

if TYPE_CHECKING:
    from src.domain.models import YtAuth
    from src.domain.ports import AuthCredentialStore, OAuthProvider
from src.shared.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class AuthorizeYtRequest:
    code: str
    url_requested: str


@dataclass(frozen=True)
class AuthorizeTikTokCookiesRequest:
    cookies: str
    client_id: str


class AuthorizeUseCase:
    """Handles OAuth authorization callbacks and persistence."""

    def __init__(
        self,
        auth_repo: AuthCredentialStore,
        yt_provider: OAuthProvider[YtAuth],
    ) -> None:
        self._auth_repo = auth_repo
        self._yt_provider = yt_provider

    async def execute_yt(self, request: AuthorizeYtRequest) -> YtAuth:
        """Exchange code and save YT credentials."""
        oauth_credentials = await self._yt_provider.step_2_exchange_code_authentication(request.url_requested)
        return self._auth_repo.add_or_update_yt_auth(oauth_credentials)

    async def execute_tiktok_cookies(self, request: AuthorizeTikTokCookiesRequest) -> TikTokAuth:
        """Persist TikTok cookie payload for uploader-based integration."""
        return self._auth_repo.add_or_update_tiktok_auth(
            TikTokAuth(
                token=request.cookies,
                refresh_token=None,
                client_id=request.client_id,
                scopes=["cookies"],
            )
        )
