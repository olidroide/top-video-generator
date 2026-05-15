from __future__ import annotations

from src.infrastructure.social.spotipy_exceptions import (
    SpotifyApiError,
    SpotifyAuthError,
    SpotifyPermissionError,
    SpotifyRateLimitError,
    map_spotipy_exception,
)


class _FakeSpotipyError(Exception):
    def __init__(self, http_status: int | None, msg: str) -> None:
        super().__init__(msg)
        self.http_status = http_status
        self.msg = msg


def test_map_spotipy_exception_returns_auth_error_for_401() -> None:
    mapped = map_spotipy_exception(_FakeSpotipyError(401, "expired"))
    assert isinstance(mapped, SpotifyAuthError)


def test_map_spotipy_exception_returns_permission_error_for_403() -> None:
    mapped = map_spotipy_exception(_FakeSpotipyError(403, "insufficient scope"))
    assert isinstance(mapped, SpotifyPermissionError)


def test_map_spotipy_exception_returns_rate_limit_error_for_429() -> None:
    mapped = map_spotipy_exception(_FakeSpotipyError(429, "slow down"))
    assert isinstance(mapped, SpotifyRateLimitError)


def test_map_spotipy_exception_returns_api_error_for_other_status() -> None:
    mapped = map_spotipy_exception(_FakeSpotipyError(500, "boom"))
    assert isinstance(mapped, SpotifyApiError)
    assert mapped.status_code == 500
