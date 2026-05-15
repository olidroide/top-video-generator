from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypeVar

from pydantic import BaseModel

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date, datetime

    from .models import (
        CanonicalVideo,
        IntegrationCheckResult,
        IntegrationPlatform,
        Platform,
        PublishingResult,
        Release,
        SpotifyAuth,
        TaskMethod,
        TaskRunState,
        TaskRunStatus,
        TikTokAuth,
        Video,
        VideoPoint,
        YtAuth,
    )

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


class IntegrationChecker(Protocol):
    @property
    def platform_name(self) -> IntegrationPlatform: ...

    @property
    def is_configured(self) -> bool: ...

    @property
    def is_publish_target(self) -> bool: ...

    async def check_connection(self) -> IntegrationCheckResult: ...


class TimeSeriesReader(Protocol):
    def get_last_timestamp(self) -> datetime | None: ...

    def get_video_points_by_date_range(self, start_time: datetime, end_time: datetime) -> list[VideoPoint]: ...


class OperationalMetricsWriter(Protocol):
    def record_metric_event(
        self,
        *,
        stage: str,
        is_error: bool,
        event_time: datetime | None = None,
    ) -> None: ...


class OperationalMetricsReader(Protocol):
    def get_metric_counts(self, *, start_time: datetime, end_time: datetime) -> dict[str, dict[str, int]]: ...


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


class ReleaseStore(Protocol):
    def get_release(self, platform: str, client_id: str, release_kind: str | None = None) -> Release | None: ...

    def is_release_at_date(self, platform: str, release_date: date, release_kind: str | None = None) -> bool: ...

    def add_or_update_release(self, release: Release) -> Release: ...


class TaskRunStateWriter(Protocol):
    def record_task_event(
        self,
        *,
        task_method: TaskMethod,
        status: TaskRunStatus,
        error_message: str | None = None,
        event_time: datetime | None = None,
    ) -> None: ...


class TaskRunStateReader(Protocol):
    def get_latest_task_event(
        self,
        *,
        task_method: TaskMethod,
        status: TaskRunStatus | None = None,
    ) -> TaskRunState | None: ...


class SpotifyPlaylistUpdater(Protocol):
    async def is_authorized(self) -> bool: ...

    async def update_original_playlist(self, playlist_id: str, song_title_list: list[str]) -> bool: ...


class VerticalVideoPipeline(Protocol):
    async def build_vertical_video(self, video_list: Sequence[Video]) -> str: ...


class HorizontalVideoPipeline(Protocol):
    async def build_horizontal_video(self, video_list: Sequence[Video]) -> tuple[str, str]: ...


class WeeklyYouTubeUploader(Protocol):
    async def upload_weekly_video(
        self,
        *,
        video_path: str,
        title: str,
        description: str,
        thumbnail_path: str,
        playlist_id: str | None,
        tags: list[str],
    ) -> str | None: ...


class VideoPublishExecutor(Protocol):
    async def publish(
        self,
        publisher: VideoPublisher,
        video_list: Sequence[CanonicalVideo],
        file_path: str,
        title: str,
        description: str,
    ) -> PublishingResult: ...


class OAuthProvider(Protocol[OAuthResultT]):
    async def step_1_get_authentication_url(self) -> str: ...

    async def step_2_exchange_code_authentication(self, authorization_value: str) -> OAuthResultT: ...
