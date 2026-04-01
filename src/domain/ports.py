from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date, datetime

    from .models import CanonicalVideo, Platform, PublishingResult, SpotifyAuth, TikTokAuth, VideoPoint, YtAuth


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
class AuthenticationReadPort(Protocol):
    def get_spotify_auth(self, client_id: str) -> SpotifyAuth | None: ...

    def get_tiktok_auth(self, client_id: str) -> TikTokAuth | None: ...

    def get_yt_auth(self, client_id: str) -> YtAuth | None: ...


@runtime_checkable
class ReleaseReadPort(Protocol):
    def is_release_at_date(self, platform: str, release_date: date) -> bool: ...


@runtime_checkable
class YouTubeOAuthProvider(Protocol):
    """Provides OAuth step-2 exchange for YouTube (sync flow)."""

    async def step_1_get_authentication_url(self) -> str: ...

    def step_2_exchange_code_authentication(self, url_requested: str) -> dict[str, Any]: ...


@runtime_checkable
class TikTokOAuthProvider(Protocol):
    """Provides OAuth step-2 exchange for TikTok (async flow)."""

    async def step_1_get_authentication_url(self) -> str: ...

    async def step_2_exchange_code_authentication(self, user_code: str) -> dict[str, Any]: ...


@runtime_checkable
class SpotifyOAuthProvider(Protocol):
    """Provides OAuth step-2 exchange for Spotify (async flow)."""

    async def step_1_get_authentication_url(self) -> str: ...

    async def step_2_exchange_code_authentication(self, user_code: str) -> dict[str, Any]: ...
