from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

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


class VideoMetadataPort(Protocol):
    def get(self, video_id: str) -> CanonicalVideo | None: ...


@runtime_checkable
class YouTubeOAuthProvider(Protocol):
    """Provides OAuth step-2 exchange for YouTube (sync flow)."""

    def step_2_exchange_code_authentication(self, url_requested: str) -> dict: ...


@runtime_checkable
class TikTokOAuthProvider(Protocol):
    """Provides OAuth step-2 exchange for TikTok (async flow)."""

    async def step_2_exchange_code_authentication(self, user_code: str) -> dict: ...


@runtime_checkable
class SpotifyOAuthProvider(Protocol):
    """Provides OAuth step-2 exchange for Spotify (async flow)."""

    async def step_2_exchange_code_authentication(self, user_code: str) -> dict: ...
