from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypeVar

from pydantic import BaseModel

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date, datetime

    from .models import CanonicalVideo, Platform, PublishingResult, SpotifyAuth, TikTokAuth, VideoPoint, YtAuth

OAuthResultT = TypeVar("OAuthResultT", bound=BaseModel)


class TrendingVideoFetcher(Protocol):
    async def fetch_trending_videos(self, *, region: str, date: str | None = None) -> list[CanonicalVideo]: ...


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


class TimeSeriesReader(Protocol):
    def get_video_points_by_date_range(self, start_time: datetime, end_time: datetime) -> list[VideoPoint]: ...


class VideoMetadataReader(Protocol):
    def get(self, video_id: str) -> CanonicalVideo | None: ...


class AuthCredentialStore(Protocol):
    def get_spotify_auth(self, client_id: str) -> SpotifyAuth | None: ...

    def get_tiktok_auth(self, client_id: str) -> TikTokAuth | None: ...

    def get_yt_auth(self, client_id: str) -> YtAuth | None: ...

    def add_or_update_spotify_auth(self, spotify_auth: SpotifyAuth) -> SpotifyAuth: ...

    def add_or_update_tiktok_auth(self, tiktok_auth: TikTokAuth) -> TikTokAuth: ...

    def add_or_update_yt_auth(self, yt_auth: YtAuth) -> YtAuth: ...


class ReleaseDateValidator(Protocol):
    def is_release_at_date(self, platform: str, release_date: date) -> bool: ...


class OAuthProvider(Protocol[OAuthResultT]):
    async def step_1_get_authentication_url(self) -> str: ...

    async def step_2_exchange_code_authentication(self, authorization_value: str) -> OAuthResultT: ...
