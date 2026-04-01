"""Unit tests for AuthorizeUseCase."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import create_autospec

from src.application.authorize_use_case import (
    AuthorizeSpotifyRequest,
    AuthorizeTikTokRequest,
    AuthorizeUseCase,
    AuthorizeYtRequest,
)
from src.domain.models import SpotifyAuth, TikTokAuth, YtAuth
from src.domain.ports import AuthCredentialStore
from src.infrastructure.social.spotify_client import SpotifyClient
from src.infrastructure.social.tiktok_client import TikTokClient
from src.infrastructure.youtube.client import YTClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_yt_provider(credentials: YtAuth | None = None) -> YTClient:
    mock: YTClient = create_autospec(YTClient, instance=True)
    mock.step_2_exchange_code_authentication.return_value = credentials or YtAuth(
        token="yt_token",
        refresh_token="yt_refresh",
        token_uri="https://oauth2.googleapis.com/token",
        client_id="yt_client_id",
        client_secret="yt_secret",
        scopes=["https://www.googleapis.com/auth/youtube"],
    )
    return mock


def make_tiktok_provider(credentials: TikTokAuth | None = None) -> TikTokClient:
    mock: TikTokClient = create_autospec(TikTokClient, instance=True)
    mock.step_2_exchange_code_authentication.return_value = credentials or TikTokAuth(
        token="tt_token",
        refresh_token="tt_refresh",
        client_id="tt_open_id",
        scopes=["user.info.basic", "video.upload"],
    )
    return mock


def make_spotify_provider(credentials: SpotifyAuth | None = None) -> SpotifyClient:
    mock: SpotifyClient = create_autospec(SpotifyClient, instance=True)
    mock.step_2_exchange_code_authentication.return_value = credentials or SpotifyAuth(
        token="sp_token",
        refresh_token="sp_refresh",
        client_id="sp_client_id",
        scopes=["playlist-modify-public", "playlist-modify-private"],
    )
    return mock


def make_use_case(_tmp_path: Path) -> AuthorizeUseCase:
    auth_repo: AuthCredentialStore = create_autospec(AuthCredentialStore, instance=True)
    auth_repo.add_or_update_yt_auth.side_effect = lambda yt_auth: yt_auth
    auth_repo.add_or_update_tiktok_auth.side_effect = lambda tiktok_auth: tiktok_auth
    auth_repo.add_or_update_spotify_auth.side_effect = lambda spotify_auth: spotify_auth
    return AuthorizeUseCase(
        auth_repo=auth_repo,
        yt_provider=make_yt_provider(),
        tiktok_provider=make_tiktok_provider(),
        spotify_provider=make_spotify_provider(),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAuthorizeUseCaseYouTube:
    async def test_execute_yt_persists_and_returns_yt_auth(self, tmp_path: Path) -> None:
        use_case = make_use_case(tmp_path)
        request = AuthorizeYtRequest(code="auth_code", url_requested="https://example.com/?code=auth_code")

        result = await use_case.execute_yt(request)

        assert isinstance(result, YtAuth)
        assert result.token == "yt_token"
        assert result.client_id == "yt_client_id"

    async def test_execute_yt_calls_provider_with_url(self, tmp_path: Path) -> None:
        _ = tmp_path
        yt_provider = make_yt_provider()
        auth_repo: AuthCredentialStore = create_autospec(AuthCredentialStore, instance=True)
        auth_repo.add_or_update_yt_auth.side_effect = lambda yt_auth: yt_auth
        use_case = AuthorizeUseCase(
            auth_repo=auth_repo,
            yt_provider=yt_provider,
            tiktok_provider=make_tiktok_provider(),
            spotify_provider=make_spotify_provider(),
        )
        url = "https://example.com/?code=abc"

        await use_case.execute_yt(AuthorizeYtRequest(code="abc", url_requested=url))

        yt_provider.step_2_exchange_code_authentication.assert_awaited_once_with(url)


class TestAuthorizeUseCaseTikTok:
    async def test_execute_tiktok_persists_and_returns_tiktok_auth(self, tmp_path: Path) -> None:
        use_case = make_use_case(tmp_path)

        result = await use_case.execute_tiktok(AuthorizeTikTokRequest(code="tt_code"))

        assert isinstance(result, TikTokAuth)
        assert result.token == "tt_token"
        assert result.client_id == "tt_open_id"

    async def test_execute_tiktok_calls_provider_with_code(self, tmp_path: Path) -> None:
        _ = tmp_path
        provider = make_tiktok_provider()
        auth_repo: AuthCredentialStore = create_autospec(AuthCredentialStore, instance=True)
        auth_repo.add_or_update_tiktok_auth.side_effect = lambda tiktok_auth: tiktok_auth
        use_case = AuthorizeUseCase(
            auth_repo=auth_repo,
            yt_provider=make_yt_provider(),
            tiktok_provider=provider,
            spotify_provider=make_spotify_provider(),
        )

        await use_case.execute_tiktok(AuthorizeTikTokRequest(code="tt_code"))

        provider.step_2_exchange_code_authentication.assert_awaited_once_with("tt_code")

    async def test_execute_tiktok_scopes_parsed_from_comma_separated(self, tmp_path: Path) -> None:
        _ = tmp_path
        provider = make_tiktok_provider(
            TikTokAuth(token="t", refresh_token="r", client_id="oid", scopes=["a", "b", "c"])
        )
        auth_repo: AuthCredentialStore = create_autospec(AuthCredentialStore, instance=True)
        auth_repo.add_or_update_tiktok_auth.side_effect = lambda tiktok_auth: tiktok_auth
        use_case = AuthorizeUseCase(
            auth_repo=auth_repo,
            yt_provider=make_yt_provider(),
            tiktok_provider=provider,
            spotify_provider=make_spotify_provider(),
        )

        result = await use_case.execute_tiktok(AuthorizeTikTokRequest(code="c"))

        assert result.scopes == ["a", "b", "c"]


class TestAuthorizeUseCaseSpotify:
    async def test_execute_spotify_persists_and_returns_spotify_auth(self, tmp_path: Path) -> None:
        use_case = make_use_case(tmp_path)

        result = await use_case.execute_spotify(AuthorizeSpotifyRequest(code="sp_code"))

        assert isinstance(result, SpotifyAuth)
        assert result.token == "sp_token"
        assert result.client_id == "sp_client_id"

    async def test_execute_spotify_calls_provider_with_code(self, tmp_path: Path) -> None:
        _ = tmp_path
        provider = make_spotify_provider()
        auth_repo: AuthCredentialStore = create_autospec(AuthCredentialStore, instance=True)
        auth_repo.add_or_update_spotify_auth.side_effect = lambda spotify_auth: spotify_auth
        use_case = AuthorizeUseCase(
            auth_repo=auth_repo,
            yt_provider=make_yt_provider(),
            tiktok_provider=make_tiktok_provider(),
            spotify_provider=provider,
        )

        await use_case.execute_spotify(AuthorizeSpotifyRequest(code="sp_code"))

        provider.step_2_exchange_code_authentication.assert_awaited_once_with("sp_code")

    async def test_execute_spotify_scopes_parsed_from_space_separated(self, tmp_path: Path) -> None:
        _ = tmp_path
        provider = make_spotify_provider(
            SpotifyAuth(
                token="t",
                refresh_token="r",
                client_id="cid",
                scopes=["playlist-modify-public", "playlist-modify-private"],
            )
        )
        auth_repo: AuthCredentialStore = create_autospec(AuthCredentialStore, instance=True)
        auth_repo.add_or_update_spotify_auth.side_effect = lambda spotify_auth: spotify_auth
        use_case = AuthorizeUseCase(
            auth_repo=auth_repo,
            yt_provider=make_yt_provider(),
            tiktok_provider=make_tiktok_provider(),
            spotify_provider=provider,
        )

        result = await use_case.execute_spotify(AuthorizeSpotifyRequest(code="c"))

        assert "playlist-modify-public" in (result.scopes or [])
        assert "playlist-modify-private" in (result.scopes or [])
