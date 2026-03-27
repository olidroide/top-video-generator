from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol, runtime_checkable

from .models import CanonicalVideo, Platform, PublishingResult, VideoPoint


@runtime_checkable
class VideoDataSource(Protocol):
    async def fetch_trending_videos(self, *, region: str, date: str | None = None) -> list[CanonicalVideo]: ...


@runtime_checkable
class VideoPublisher(Protocol):
    @property
    def platform_name(self) -> Platform: ...
    @property
    def is_enabled(self) -> bool: ...
    async def publish_video(
        self,
        video_list: Sequence[CanonicalVideo],
        file_path: str,
        title: str,
        description: str,
    ) -> PublishingResult: ...


class TimeSeriesPort(Protocol):
    def get_video_points_by_date_range(self, start_time: datetime, end_time: datetime) -> list[VideoPoint]: ...
