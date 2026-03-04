from enum import StrEnum
from datetime import datetime, timezone
from typing import Annotated
from pydantic import BaseModel, computed_field

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
    views_growth: int
    score: float
    score_previous: float
    score_status: VideoScoreStatus
    thumbnail_url: str

    @computed_field
    @property
    def yt_url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"

    @computed_field
    @property
    def title_cleaned(self) -> str:
        # Simple cleaning: strip and collapse whitespace
        return " ".join(self.title.strip().split())

class PublishingResult(BaseModel, frozen=True):
    platform: Platform
    success: bool
    published_id: str | None = None
    published_at: datetime = datetime.now(timezone.utc)
    error: str | None = None
