"""Integration tests for AuthenticationRepository."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.domain.models import SpotifyAuth, TikTokAuth, YtAuth
from src.infrastructure.storage.auth_repository import AuthenticationRepository


@pytest.fixture
def repo(tmp_path: Path) -> AuthenticationRepository:
    return AuthenticationRepository(db_path=tmp_path / "test_auth.json")


class TestYtAuth:
    def test_add_and_get_yt_auth(self, repo: AuthenticationRepository) -> None:
        auth = YtAuth(
            token="tok",
            refresh_token="ref",
            token_uri="https://oauth2.googleapis.com/token",
            client_id="yt_user",
            client_secret="secret",
            scopes=["https://www.googleapis.com/auth/youtube"],
        )
        repo.add_or_update_yt_auth(auth)

        result = repo.get_yt_auth("yt_user")
        assert result is not None
        assert result.token == "tok"
        assert result.client_id == "yt_user"

    def test_get_yt_auth_returns_none_for_unknown(self, repo: AuthenticationRepository) -> None:
        assert repo.get_yt_auth("nobody") is None

    def test_update_yt_auth_overwrites_token(self, repo: AuthenticationRepository) -> None:
        auth = YtAuth(token="old_token", client_id="yt_user")
        repo.add_or_update_yt_auth(auth)
        repo.add_or_update_yt_auth(YtAuth(token="new_token", client_id="yt_user"))

        result = repo.get_yt_auth("yt_user")
        assert result is not None
        assert result.token == "new_token"


class TestTikTokAuth:
    def test_add_and_get_tiktok_auth(self, repo: AuthenticationRepository) -> None:
        auth = TikTokAuth(
            token="tt_tok",
            refresh_token="tt_ref",
            client_id="tt_openid",
            scopes=["user.info.basic"],
        )
        repo.add_or_update_tiktok_auth(auth)

        result = repo.get_tiktok_auth("tt_openid")
        assert result is not None
        assert result.token == "tt_tok"

    def test_get_tiktok_auth_returns_none_for_unknown(self, repo: AuthenticationRepository) -> None:
        assert repo.get_tiktok_auth("nobody") is None


class TestSpotifyAuth:
    def test_add_and_get_spotify_auth(self, repo: AuthenticationRepository) -> None:
        auth = SpotifyAuth(
            token="sp_tok",
            refresh_token="sp_ref",
            client_id="sp_user",
            scopes=["playlist-modify-public"],
        )
        repo.add_or_update_spotify_auth(auth)

        result = repo.get_spotify_auth("sp_user")
        assert result is not None
        assert result.token == "sp_tok"
        assert "playlist-modify-public" in (result.scopes or [])

    def test_get_spotify_auth_returns_none_for_unknown(self, repo: AuthenticationRepository) -> None:
        assert repo.get_spotify_auth("nobody") is None

    def test_update_spotify_auth_overwrites_token(self, repo: AuthenticationRepository) -> None:
        repo.add_or_update_spotify_auth(SpotifyAuth(token="old", client_id="sp_user"))
        repo.add_or_update_spotify_auth(SpotifyAuth(token="updated", client_id="sp_user"))

        result = repo.get_spotify_auth("sp_user")
        assert result is not None
        assert result.token == "updated"
