"""View models for SSR templates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

from src.domain.models import IntegrationCheckResult, IntegrationCheckStatus

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from src.application.get_setup_page_use_case import GetSetupPageResult
    from src.config.settings import AppSettings
    from src.domain.models import SpotifyAuth, TikTokAuth, Video, YtAuth


@dataclass(frozen=True)
class VideoCardViewModel:
    """Presentation model for a video row."""

    score: int | None
    score_previous: int | None
    score_status: str | None
    yt_video_title_cleaned: str
    channel_name: str
    yt_video_url: str
    yt_video_thumbnail_url: str

    @classmethod
    def from_domain(cls, video: Video) -> VideoCardViewModel:
        return cls(
            score=video.score,
            score_previous=video.score_previous,
            score_status=video.score_status.value if video.score_status else None,
            yt_video_title_cleaned=video.title_cleaned,
            channel_name=video.channel.name if video.channel and video.channel.name else "",
            yt_video_url=video.yt_video_url,
            yt_video_thumbnail_url=video.yt_video_thumbnail_url,
        )


@dataclass(frozen=True)
class IndexPageViewModel:
    """Presentation model for the top-videos index page."""

    title_page: str
    video_list: tuple[VideoCardViewModel, ...]
    timeseries_daily_date: date
    timeseries_previous_href: str
    timeseries_next_href: str | None
    timeseries_daily_href: str
    timeseries_weekly_href: str
    is_weekly: bool
    yt_video_published: bool
    credentials_owner: bool

    @property
    def timeseries_mode_label(self) -> str:
        return "Weekly" if self.is_weekly else "Daily"


def build_index_page_view_model(
    *,
    title_flag: str,
    videos: Sequence[Video],
    current_date: date,
    today: date,
    min_daily_date: date,
    is_weekly: bool,
    yt_video_published: bool,
    credentials_owner: bool,
) -> IndexPageViewModel:
    """Build the page model for the top-videos index SSR template."""
    previous_day = current_date - timedelta(days=1)
    return IndexPageViewModel(
        title_page=f"{title_flag} \U0001f51d VIDEO GENERATOR",
        video_list=tuple(VideoCardViewModel.from_domain(video) for video in videos),
        timeseries_daily_date=current_date,
        timeseries_previous_href=f"?daily={previous_day:%Y-%m-%d}" if previous_day >= min_daily_date else "",
        timeseries_next_href=f"?daily={(current_date + timedelta(days=1)):%Y-%m-%d}" if current_date < today else None,
        timeseries_daily_href=f"?daily={current_date:%Y-%m-%d}",
        timeseries_weekly_href=f"?weekly={current_date:%Y-%m-%d}",
        is_weekly=is_weekly,
        yt_video_published=yt_video_published,
        credentials_owner=credentials_owner,
    )


@dataclass(frozen=True)
class SetupPageViewModel:
    """Presentation model for the auth setup page."""

    page_title: str
    yt_authentication_url: str | None
    yt_credentials: YtAuth | None
    tiktok_authentication_url: str | None
    tiktok_credentials: TikTokAuth | None
    spotify_authentication_url: str | None
    spotify_credentials: SpotifyAuth | None


def build_setup_page_view_model(result: GetSetupPageResult) -> SetupPageViewModel:
    """Build the page model for the auth setup SSR template."""
    return SetupPageViewModel(
        page_title="Setup Platform Connections",
        yt_authentication_url=result.yt_authentication_url,
        yt_credentials=result.yt_credentials,
        tiktok_authentication_url=result.tiktok_authentication_url,
        tiktok_credentials=result.tiktok_credentials,
        spotify_authentication_url=result.spotify_authentication_url,
        spotify_credentials=result.spotify_credentials,
    )


@dataclass(frozen=True)
class PlatformLiveCheckViewModel:
    """Presentation model for the latest live integration check."""

    state: str
    label: str
    message: str


@dataclass(frozen=True)
class PlatformConnectionViewModel:
    """Presentation model for a single platform connection card."""

    slug: str
    name: str
    icon_class: str
    is_connected: bool
    is_configured: bool
    is_publish_target: bool
    auth_url: str | None
    connected_id: str | None
    auth_type: str
    can_run_check: bool
    check_action_label: str
    live_check: PlatformLiveCheckViewModel


@dataclass(frozen=True)
class AdminConnectionsViewModel:
    """Presentation model for the admin connections dashboard."""

    platforms: tuple[PlatformConnectionViewModel, ...]

    @property
    def connected_count(self) -> int:
        return sum(1 for platform in self.platforms if platform.is_connected)

    @property
    def total_count(self) -> int:
        return len(self.platforms)


def _build_live_check_view_model(
    *,
    is_configured: bool,
    is_publish_target: bool,
    check_result: IntegrationCheckResult | None,
) -> PlatformLiveCheckViewModel:
    if check_result is None:
        if not is_configured:
            return PlatformLiveCheckViewModel(
                state="na",
                label="NOT CONFIGURED",
                message="Missing local configuration.",
            )
        return PlatformLiveCheckViewModel(
            state="idle",
            label="READY",
            message="Run a live check.",
        )

    if check_result.status == IntegrationCheckStatus.OK:
        return PlatformLiveCheckViewModel(
            state="on",
            label="VERIFIED",
            message=check_result.message
            or ("Publishing API reachable." if is_publish_target else "Integration API reachable."),
        )

    if check_result.status == IntegrationCheckStatus.NOT_CONFIGURED:
        return PlatformLiveCheckViewModel(
            state="na",
            label="NOT CONFIGURED",
            message=check_result.message or "Missing local configuration.",
        )

    return PlatformLiveCheckViewModel(
        state="off",
        label="FAILED",
        message=check_result.message or "Live check failed.",
    )


def _build_platform_connection_view_model(
    *,
    slug: str,
    name: str,
    icon_class: str,
    is_connected: bool,
    is_configured: bool,
    is_publish_target: bool,
    auth_url: str | None,
    connected_id: str | None,
    auth_type: str,
    check_result: IntegrationCheckResult | None,
) -> PlatformConnectionViewModel:
    return PlatformConnectionViewModel(
        slug=slug,
        name=name,
        icon_class=icon_class,
        is_connected=is_connected,
        is_configured=is_configured,
        is_publish_target=is_publish_target,
        auth_url=auth_url,
        connected_id=connected_id,
        auth_type=auth_type,
        can_run_check=is_configured,
        check_action_label="Check publish" if is_publish_target else "Check connection",
        live_check=_build_live_check_view_model(
            is_configured=is_configured,
            is_publish_target=is_publish_target,
            check_result=check_result,
        ),
    )


def get_platform_connection_view_model(
    vm: AdminConnectionsViewModel,
    slug: str,
) -> PlatformConnectionViewModel | None:
    return next((platform for platform in vm.platforms if platform.slug == slug), None)


def build_admin_connections_view_model(
    result: GetSetupPageResult,
    settings: AppSettings,
    check_results: Mapping[str, IntegrationCheckResult] | None = None,
) -> AdminConnectionsViewModel:
    """Build the page model for the admin connections SSR template."""
    checks = dict(check_results or {})
    yt = _build_platform_connection_view_model(
        slug="youtube",
        name="YouTube",
        icon_class="fab fa-youtube",
        is_connected=result.yt_credentials is not None,
        is_configured=bool(settings.yt_client_secret_file),
        is_publish_target=True,
        auth_url=result.yt_authentication_url,
        connected_id=settings.yt_auth_user_id,
        auth_type="OAUTH 2.0",
        check_result=checks.get("youtube"),
    )
    tiktok = _build_platform_connection_view_model(
        slug="tiktok",
        name="TikTok",
        icon_class="fab fa-tiktok",
        is_connected=result.tiktok_credentials is not None,
        is_configured=bool(settings.tiktok_client_key and settings.tiktok_client_secret),
        is_publish_target=True,
        auth_url=result.tiktok_authentication_url,
        connected_id=settings.tiktok_user_openid,
        auth_type="OAUTH 2.0",
        check_result=checks.get("tiktok"),
    )
    spotify = _build_platform_connection_view_model(
        slug="spotify",
        name="Spotify",
        icon_class="fab fa-spotify",
        is_connected=result.spotify_credentials is not None,
        is_configured=bool(settings.spotify_client_id and settings.spotify_client_secret),
        is_publish_target=False,
        auth_url=result.spotify_authentication_url,
        connected_id=settings.spotify_user_id,
        auth_type="OAUTH 2.0",
        check_result=checks.get("spotify"),
    )
    instagram = _build_platform_connection_view_model(
        slug="instagram",
        name="Instagram",
        icon_class="fab fa-instagram",
        is_connected=settings.is_instagram_configured,
        is_configured=settings.is_instagram_configured,
        is_publish_target=True,
        auth_url=None,
        connected_id=settings.instagram_client_username,
        auth_type="CREDENTIAL",
        check_result=checks.get("instagram"),
    )
    return AdminConnectionsViewModel(platforms=(yt, tiktok, spotify, instagram))


@dataclass(frozen=True)
class HealthCheckItemViewModel:
    """Presentation model for a single system health check."""

    name: str
    status: str  # "ok" | "error"
    message: str


@dataclass(frozen=True)
class AdminHealthViewModel:
    """Presentation model for the system health section."""

    overall: str  # "healthy" | "unhealthy"
    version: str
    checks: tuple[HealthCheckItemViewModel, ...]


def build_admin_health_view_model(health: dict[str, Any]) -> AdminHealthViewModel:
    """Build the health section view model from raw health-check data."""
    raw_checks: dict[str, dict[str, str]] = health.get("checks", {})  # type: ignore[assignment]
    return AdminHealthViewModel(
        overall=str(health.get("status", "unhealthy")),
        version=str(health.get("version", "—")),
        checks=tuple(
            HealthCheckItemViewModel(
                name=name,
                status=c.get("status", "error"),
                message=c.get("message", ""),
            )
            for name, c in raw_checks.items()
        ),
    )
