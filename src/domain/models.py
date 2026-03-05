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
        title = self.title.strip()
        for token in _NOISE_TOKENS:
            title = title.replace(token, "")
        return " ".join(title.split())


class PublishingResult(BaseModel, frozen=True):
    platform: Platform
    success: bool
    published_id: str | None = None
    published_at: datetime = datetime.now(UTC)
    error: str | None = None


# ============================================================================
# Persistence Layer Models (Infrastructure)
# ============================================================================


class Channel(BaseModel):
    """Represents a YouTube channel."""

    channel_id: str | None = None
    name: str | None = None


class TimeseriesRange(StrEnum):
    """Time range for fetching timeseries data."""

    DAILY = "daily"
    WEEKLY = "weekly"


class ReleasePlatform(StrEnum):
    """Platforms where videos can be released."""

    YOUTUBE = "YOUTUBE"
    TIKTOK = "TIKTOK"
    INSTAGRAM = "INSTAGRAM"
    SPOTIFY = "SPOTIFY"


class Release(BaseModel):
    """Represents a published release on a platform."""

    platform: str | None = None
    client_id: str | None = None
    release_id: str | None = None
    published_at: float | None = None


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
        regex = r"#(\w+)"
        hashtag_list = re.findall(regex, self.description)
        return [f"#{hashtag}" for hashtag in hashtag_list]

    @property
    def yt_video_thumbnail_url(self) -> str:
        """YouTube thumbnail URL."""
        return f"https://i.ytimg.com/vi/{self.video_id}/maxresdefault.jpg"

    @property
    def yt_video_url(self) -> str:
        """YouTube video URL."""
        return f"https://www.youtube.com/watch?v={self.video_id}"

    @property
    def yt_video_title_cleaned(self) -> str:
        """Clean title by removing common noise tokens."""
        if not self.title:
            return ""
        title = self.title
        title = title.replace("(Video)", "")
        title = title.replace("(Music Video)", "")
        title = title.replace("Official Video", "")
        title = title.replace("#Video", "")
        title = title.replace("Full Video", "")
        title = title.replace("(video)", "")
        title = title.replace("Full Song", "")
        title = title.replace(" - ", " ")
        title = title.replace("()", "")
        title = title.replace("( )", "")
        title = title.replace("(Full )", "")
        title = title.replace(": ", " ")
        title = title.replace("  ", " ")
        return title.strip()


class TimePoint(BaseModel):
    """Base class for time-series data points."""

    time: datetime


class VideoPoint(Video, TimePoint):
    """Video data with timestamp (timeseries point in TinyFlux)."""

    pass
