from __future__ import annotations

import re
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, computed_field

_NOISE_TOKENS: frozenset[str] = frozenset(
    {
        "(Video)",
        "(Music Video)",
        "Official Video",
        "#Video",
        "Full Video",
        "(video)",
    }
)


class Platform(StrEnum):
    YOUTUBE = "YOUTUBE"
    TIKTOK = "TIKTOK"
    INSTAGRAM = "INSTAGRAM"
    SPOTIFY = "SPOTIFY"


class IntegrationPlatform(StrEnum):
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"
    SPOTIFY = "spotify"


class IntegrationCheckStatus(StrEnum):
    OK = "ok"
    ERROR = "error"
    NOT_CONFIGURED = "not_configured"


class VideoScoreStatus(StrEnum):
    NEW = "NEW"
    UP = "UP"
    DOWN = "DOWN"
    EQUAL = "EQUAL"


class CanonicalVideo(BaseModel, frozen=True):
    video_id: str
    title: str
    channel_name: str
    views: int
    views_growth: int = 0
    score: float = 0.0
    score_previous: float | None = None
    description: str = ""
    duration_seconds: float = 0.0
    likes: int = 0
    thumbnail_url: str | None = None

    @computed_field
    @property
    def yt_url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"

    @computed_field
    @property
    def title_cleaned(self) -> str:
        """Clean title by removing common noise tokens."""
        return _clean_title(self.title)

    @computed_field
    @property
    def yt_video_title_cleaned(self) -> str:
        """Compatibility alias for existing call sites."""
        return self.title_cleaned


class PublishingResult(BaseModel, frozen=True):
    platform: Platform
    success: bool
    published_id: str | None = None
    published_at: datetime = datetime.now(UTC)
    error: str | None = None


class IntegrationCheckResult(BaseModel, frozen=True):
    platform: IntegrationPlatform
    status: IntegrationCheckStatus
    is_configured: bool
    is_publish_target: bool
    message: str | None = None
    checked_at: datetime = datetime.now(UTC)


class Channel(BaseModel):
    """YouTube channel metadata."""

    name: str | None = None
    channel_id: str | None = None


class SpotifyAuth(BaseModel):
    """Spotify OAuth2 credentials."""

    token: str | None = None
    refresh_token: str | None = None
    client_id: str | None = None
    scopes: list[str] | None = None


class TikTokAuth(BaseModel):
    """TikTok OAuth2 credentials."""

    token: str | None = None
    refresh_token: str | None = None
    client_id: str | None = None
    scopes: list[str] | None = None


class YtAuth(BaseModel):
    """YouTube OAuth2 credentials."""

    token: str | None = None
    refresh_token: str | None = None
    token_uri: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    scopes: list[str] | None = None


class TimeseriesRange(StrEnum):
    """Time range for fetching timeseries data."""

    DAILY = "daily"
    WEEKLY = "weekly"


class ReleaseKind(StrEnum):
    """Release categories used for idempotency."""

    DAILY_VERTICAL = "DAILY_VERTICAL"
    WEEKLY_HORIZONTAL = "WEEKLY_HORIZONTAL"


class Release(BaseModel):
    """Represents a published release on a platform."""

    platform: str | None = None
    client_id: str | None = None
    release_kind: str | None = None
    release_id: str | None = None
    published_at: float | None = None


class Video(BaseModel):
    """Video metadata (persisted in TinyDB)."""

    video_id: str
    views: int = 0
    likes: int = 0
    views_growth: int | None = None
    score: int | None = None
    score_status: VideoScoreStatus | None = None
    score_previous: int | None = None
    title: str | None = None
    description: str | None = None
    channel: Channel | None = None
    duration: int | None = None

    @property
    def hashtags_in_description(self) -> list[str]:
        """Extract hashtags from description."""
        if not self.description:
            return []
        hashtag_list = re.findall(r"#(\w+)", self.description)
        return [f"#{hashtag}" for hashtag in hashtag_list]

    @property
    def title_cleaned(self) -> str:
        """Clean title by removing common noise tokens."""
        return _clean_title(self.title)

    @property
    def yt_video_thumbnail_url(self) -> str:
        """YouTube thumbnail URL."""
        return f"https://i.ytimg.com/vi/{self.video_id}/maxresdefault.jpg"

    @property
    def yt_video_url(self) -> str:
        """YouTube video URL."""
        return f"https://www.youtube.com/watch?v={self.video_id}"


class VideoPoint(BaseModel):
    """Video metadata point for timeseries tracking."""

    time: datetime
    video_id: str
    title: str | None = None
    description: str | None = None
    channel: Channel | None = None
    views: int = 0
    likes: int = 0
    views_growth: int | None = None
    score: int | None = None
    score_previous: int | None = None
    score_status: VideoScoreStatus | None = None
    duration: int | None = None


def _clean_title(raw_title: str | None) -> str:
    """Shared title cleaner used by canonical and legacy video models."""
    if not raw_title:
        return ""

    title = raw_title.strip()
    for token in _NOISE_TOKENS:
        title = title.replace(token, "")

    title = title.replace("Full Song", "")
    title = title.replace(" - ", " ")
    title = title.replace("()", "")
    title = title.replace("( )", "")
    title = title.replace("(Full )", "")
    title = title.replace(": ", " ")
    return " ".join(title.split())
