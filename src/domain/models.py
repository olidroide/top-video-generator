from __future__ import annotations

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
