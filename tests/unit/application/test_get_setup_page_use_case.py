"""Unit tests for GetSetupPageUseCase."""

from __future__ import annotations

from unittest.mock import create_autospec

from src.application.get_setup_page_use_case import GetSetupPageRequest, GetSetupPageUseCase
from src.domain.models import SpotifyAuth, TikTokAuth, YtAuth
from src.domain.ports import AuthCredentialStore
from src.infrastructure.social.spotify_client import SpotifyClient
from src.infrastructure.youtube.yt_client import YTClient


def _build_auth_repo() -> AuthCredentialStore:
    auth_repo: AuthCredentialStore = create_autospec(AuthCredentialStore, instance=True)
    auth_repo.get_yt_auth.side_effect = lambda client_id: (
        YtAuth(client_id=client_id)
        if client_id == "yt-session"
        else YtAuth(client_id=client_id)
        if client_id == "yt-user"
        else None
    )
    auth_repo.get_tiktok_auth.side_effect = lambda client_id: (
        TikTokAuth(client_id=client_id)
        if client_id == "tt-session"
        else TikTokAuth(client_id=client_id)
        if client_id == "tt-user"
        else None
    )
    auth_repo.get_spotify_auth.side_effect = lambda client_id: (
        SpotifyAuth(client_id=client_id)
        if client_id == "sp-session"
        else SpotifyAuth(client_id=client_id)
        if client_id == "sp-user"
        else None
    )
    return auth_repo


def _build_youtube_provider() -> YTClient:
    provider: YTClient = create_autospec(YTClient, instance=True)
    provider.step_1_get_authentication_url.return_value = "https://yt.example/auth"
    return provider


def _build_spotify_provider() -> SpotifyClient:
    provider: SpotifyClient = create_autospec(SpotifyClient, instance=True)
    provider.step_1_get_authentication_url.return_value = "https://sp.example/auth"
    return provider


class TestGetSetupPageUseCase:
    async def test_returns_completed_state_when_setup_is_finished(self) -> None:
        use_case = GetSetupPageUseCase(
            _build_auth_repo(),
            _build_youtube_provider(),
            _build_spotify_provider(),
        )

        result = await use_case.execute(
            GetSetupPageRequest(
                yt_session_client_id=None,
                tiktok_session_client_id=None,
                spotify_session_client_id=None,
                yt_auth_user_id="yt-user",
                tiktok_user_openid="tt-user",
                spotify_user_id="sp-user",
            )
        )

        assert result.is_completed is True
        assert result.yt_authentication_url is None
        assert result.tiktok_authentication_url is None
        assert result.spotify_authentication_url is None

    async def test_returns_session_credentials_without_urls_when_incomplete(self) -> None:
        auth_repo: AuthCredentialStore = create_autospec(AuthCredentialStore, instance=True)
        auth_repo.get_yt_auth.side_effect = lambda client_id: (
            YtAuth(client_id=client_id) if client_id == "yt-session" else None
        )
        auth_repo.get_tiktok_auth.side_effect = lambda client_id: (
            TikTokAuth(client_id=client_id) if client_id == "tt-session" else None
        )
        auth_repo.get_spotify_auth.side_effect = lambda client_id: (
            SpotifyAuth(client_id=client_id) if client_id == "sp-session" else None
        )

        use_case = GetSetupPageUseCase(
            auth_repo,
            _build_youtube_provider(),
            _build_spotify_provider(),
        )

        result = await use_case.execute(
            GetSetupPageRequest(
                yt_session_client_id="yt-session",
                tiktok_session_client_id="tt-session",
                spotify_session_client_id="sp-session",
                yt_auth_user_id="yt-user",
                tiktok_user_openid="tt-user",
                spotify_user_id="sp-user",
            )
        )

        assert result.is_completed is False
        assert result.yt_credentials is not None and result.yt_credentials.client_id == "yt-session"
        assert result.tiktok_credentials is not None and result.tiktok_credentials.client_id == "tt-session"
        assert result.spotify_credentials is not None and result.spotify_credentials.client_id == "sp-session"
        assert result.yt_authentication_url is None
        assert result.tiktok_authentication_url is None
        assert result.spotify_authentication_url is None

    async def test_returns_auth_urls_when_session_credentials_missing(self) -> None:
        auth_repo: AuthCredentialStore = create_autospec(AuthCredentialStore, instance=True)
        auth_repo.get_yt_auth.return_value = None
        auth_repo.get_tiktok_auth.return_value = None
        auth_repo.get_spotify_auth.return_value = None

        use_case = GetSetupPageUseCase(
            auth_repo,
            _build_youtube_provider(),
            _build_spotify_provider(),
        )

        result = await use_case.execute(
            GetSetupPageRequest(
                yt_session_client_id=None,
                tiktok_session_client_id=None,
                spotify_session_client_id=None,
                yt_auth_user_id="yt-user",
                tiktok_user_openid="tt-user",
                spotify_user_id="sp-user",
            )
        )

        assert result.is_completed is False
        assert result.yt_authentication_url == "https://yt.example/auth"
        assert result.tiktok_authentication_url is None
        assert result.spotify_authentication_url == "https://sp.example/auth"
