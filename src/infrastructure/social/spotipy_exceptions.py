"""Spotipy exception normalization for repository-specific error handling."""

from __future__ import annotations

from dataclasses import dataclass

HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_TOO_MANY_REQUESTS = 429


class SpotifyClientError(RuntimeError):
    """Base error raised by the Spotipy-backed Spotify client."""


@dataclass(slots=True)
class SpotifyApiError(SpotifyClientError):
    """Generic Spotify API error."""

    status_code: int | None
    detail: str

    def __str__(self) -> str:
        status = self.status_code if self.status_code is not None else "unknown"
        return f"Spotify API error (status={status}): {self.detail}"


class SpotifyAuthError(SpotifyClientError):
    """Authentication or token lifecycle error."""


class SpotifyPermissionError(SpotifyClientError):
    """Scope/permission mismatch error."""


class SpotifyRateLimitError(SpotifyClientError):
    """Rate limit error surfaced by Spotify."""


def map_spotipy_exception(exc: Exception) -> SpotifyClientError:
    """Map Spotipy exceptions to stable repository-level exception types."""
    status = getattr(exc, "http_status", None)
    raw_msg = getattr(exc, "msg", None)
    message = raw_msg if isinstance(raw_msg, str) and raw_msg else str(exc)

    if status == HTTP_UNAUTHORIZED:
        return SpotifyAuthError(f"Token expired or invalid: {message}")
    if status == HTTP_FORBIDDEN:
        return SpotifyPermissionError(f"Insufficient scope: {message}")
    if status == HTTP_TOO_MANY_REQUESTS:
        return SpotifyRateLimitError(f"Rate limit reached: {message}")

    return SpotifyApiError(status_code=status, detail=message)
