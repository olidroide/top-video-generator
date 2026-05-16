"""View models for SSR templates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

from src.domain.models import IntegrationCheckResult, IntegrationCheckStatus, Platform

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from src.application.get_admin_task_status_use_case import TaskStatusResult
    from src.application.get_setup_page_use_case import GetSetupPageResult
    from src.config.settings import AppSettings
    from src.domain.models import SpotifyAuth, TikTokAuth, Video, YtAuth


_SPOTIFY_REAUTH_PREFIX = "Spotify authorization is invalid or expired."
_SECONDS_PER_HOUR = 3600
_HOURS_PER_DAY = 24
_HOURS_PER_WEEK = _HOURS_PER_DAY * 7


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

    if isinstance(check_result.message, str) and check_result.message.startswith(_SPOTIFY_REAUTH_PREFIX):
        return PlatformLiveCheckViewModel(
            state="off",
            label="REAUTH REQUIRED",
            message=check_result.message,
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
    effective_is_configured = (
        False
        if check_result is not None and check_result.status == IntegrationCheckStatus.NOT_CONFIGURED
        else is_configured
    )
    effective_is_connected = is_connected and effective_is_configured

    return PlatformConnectionViewModel(
        slug=slug,
        name=name,
        icon_class=icon_class,
        is_connected=effective_is_connected,
        is_configured=effective_is_configured,
        is_publish_target=is_publish_target,
        auth_url=auth_url,
        connected_id=connected_id,
        auth_type=auth_type,
        can_run_check=effective_is_configured,
        check_action_label="Check publish" if is_publish_target else "Check connection",
        live_check=_build_live_check_view_model(
            is_configured=effective_is_configured,
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
        is_configured=bool(settings.tiktok_cookies_file or settings.tiktok_user_openid),
        is_publish_target=True,
        auth_url=None,
        connected_id=settings.tiktok_user_openid,
        auth_type="COOKIE",
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


@dataclass(frozen=True)
class AdminMetricItemViewModel:
    """Presentation model for a single admin metric row."""

    key: str
    label: str
    count: int
    errors: int
    error_rate_label: str


@dataclass(frozen=True)
class AdminMetricsPanelViewModel:
    """Presentation model for the admin metrics section."""

    metrics: tuple[AdminMetricItemViewModel, ...]


def _format_error_rate(*, count: int, errors: int) -> str:
    total = count + errors
    if total == 0:
        return "0%"
    return f"{(errors / total) * 100:.1f}%"


def build_admin_metrics_view_model(raw_metrics: Mapping[str, int]) -> AdminMetricsPanelViewModel:
    """Build the metrics section view model from in-memory counters."""
    metrics: list[AdminMetricItemViewModel] = []
    for key, label in (
        ("fetch", "Fetch"),
        ("processing", "Processing"),
        ("upload", "Upload"),
    ):
        count = int(raw_metrics.get(f"{key}_count", 0))
        errors = int(raw_metrics.get(f"{key}_errors", 0))
        metrics.append(
            AdminMetricItemViewModel(
                key=key,
                label=label,
                count=count,
                errors=errors,
                error_rate_label=_format_error_rate(count=count, errors=errors),
            )
        )
    return AdminMetricsPanelViewModel(metrics=tuple(metrics))


@dataclass(frozen=True)
class AdminTaskViewModel:
    """Presentation model for a single admin task status."""

    name: str
    last_run_label: str
    hours_since: int | None
    older_than_24h: bool
    source: str
    applicable: bool
    warning_message: str | None
    last_status: str | None
    last_error: str | None
    action_label: str
    detail_rows: tuple[str, ...] = ()
    is_running: bool = False


@dataclass(frozen=True)
class AdminTasksPanelViewModel:
    """Presentation model for the admin tasks panel."""

    tasks: tuple[AdminTaskViewModel, ...]
    any_running: bool = False


def build_time_label(timestamp: float | None) -> str:
    """
    Convert timestamp to human-readable label.

    Args:
        timestamp: Unix timestamp or None

    Returns:
        - "Never" if timestamp is None
        - "N h ago" format if within 24 hours
        - ISO 8601 format if older
    """
    if timestamp is None:
        return "Never"

    from datetime import UTC, datetime

    now = datetime.now(UTC).timestamp()
    hours = (now - timestamp) / _SECONDS_PER_HOUR

    if hours < 1:
        return "just now"
    if hours < _HOURS_PER_DAY:
        return f"{int(hours)} h ago"
    # Return ISO 8601 format
    dt = datetime.fromtimestamp(timestamp, tz=UTC)
    return dt.isoformat(timespec="minutes")


def build_admin_tasks_view_model(
    task_status: TaskStatusResult,
) -> AdminTasksPanelViewModel:
    """
    Build admin tasks panel from persisted task execution status.

    Args:
        task_status: Result from GetAdminTaskStatusUseCase

    Returns:
        AdminTasksPanelViewModel with task statuses
    """
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    latest_status = task_status.latest_status_by_method
    latest_errors = task_status.latest_error_by_method

    running_methods = task_status.running_methods

    fetch_last_float = task_status.fetch_last_timestamp
    fetch_hours = (now.timestamp() - fetch_last_float) / _SECONDS_PER_HOUR if fetch_last_float else None
    fetch_older_than_24h = fetch_hours is not None and fetch_hours >= _HOURS_PER_DAY
    fetch_status = latest_status.get("fetch")
    fetch_error = latest_errors.get("fetch")
    fetch_failed = fetch_status == "failed"

    # Daily vertical releases
    daily_task_vm = AdminTaskViewModel(
        name="Fetch Data",
        last_run_label=build_time_label(fetch_last_float),
        hours_since=int(fetch_hours) if fetch_hours else None,
        older_than_24h=fetch_older_than_24h,
        source="task_run_state" if fetch_last_float else "never",
        applicable=True,
        warning_message=(
            "Last fetch run failed. Retry recommended."
            if fetch_failed
            else ("No videos fetched in 24+ hours" if fetch_older_than_24h else None)
        ),
        last_status=fetch_status,
        last_error=fetch_error,
        action_label="Retry Fetch" if fetch_failed else "Trigger Fetch",
        is_running="fetch" in running_methods,
    )

    daily_timestamp = task_status.daily_last_timestamp
    daily_hours = (now.timestamp() - daily_timestamp) / _SECONDS_PER_HOUR if daily_timestamp else None
    daily_older_than_24h = daily_hours is not None and daily_hours >= _HOURS_PER_DAY
    daily_status = latest_status.get("daily")
    daily_error = latest_errors.get("daily")
    daily_failed = daily_status == "failed"

    latest_artifact_path = task_status.latest_video_artifact_path
    latest_artifact_ts = task_status.latest_video_artifact_timestamp
    platform_rows = tuple(
        f"{platform.value}: {build_time_label(task_status.daily_publish_timestamps_by_platform.get(platform.value))}"
        for platform in Platform
    )
    artifact_rows = (
        (
            f"Last processed video: {build_time_label(latest_artifact_ts)}",
            f"Artifact path: {latest_artifact_path}",
        )
        if latest_artifact_path and latest_artifact_ts
        else ()
    )

    source = "task_run_state" if daily_timestamp else ("videos_folder" if latest_artifact_path else "never")

    daily_publish_task_vm = AdminTaskViewModel(
        name="Daily Vertical Videos",
        last_run_label=build_time_label(daily_timestamp),
        hours_since=int(daily_hours) if daily_hours else None,
        older_than_24h=daily_older_than_24h,
        source=source,
        applicable=True,
        warning_message=(
            "Last daily run failed. Retry recommended."
            if daily_failed
            else ("No daily publish in 24+ hours" if daily_older_than_24h else None)
        ),
        last_status=daily_status,
        last_error=daily_error,
        action_label="Retry Daily" if daily_failed else "Trigger Daily",
        detail_rows=artifact_rows + platform_rows,
        is_running="daily" in running_methods,
    )

    # Weekly horizontal YouTube
    weekly_yt_timestamp = task_status.weekly_last_timestamp
    weekly_yt_hours = (now.timestamp() - weekly_yt_timestamp) / _SECONDS_PER_HOUR if weekly_yt_timestamp else None
    weekly_yt_older_than_24h = weekly_yt_hours is not None and weekly_yt_hours >= _HOURS_PER_WEEK
    weekly_status = latest_status.get("weekly")
    weekly_error = latest_errors.get("weekly")
    weekly_failed = weekly_status == "failed"

    weekly_yt_task_vm = AdminTaskViewModel(
        name="Weekly Horizontal (YouTube)",
        last_run_label=build_time_label(weekly_yt_timestamp),
        hours_since=int(weekly_yt_hours) if weekly_yt_hours else None,
        older_than_24h=weekly_yt_older_than_24h,
        source="task_run_state" if weekly_yt_timestamp else "never",
        applicable=True,
        warning_message=(
            "Last weekly run failed. Retry recommended."
            if weekly_failed
            else ("No weekly publish in 7+ days" if weekly_yt_older_than_24h else None)
        ),
        last_status=weekly_status,
        last_error=weekly_error,
        action_label="Retry Weekly" if weekly_failed else "Trigger Weekly",
        is_running="weekly" in running_methods,
    )

    tasks: list[AdminTaskViewModel] = [daily_task_vm, daily_publish_task_vm, weekly_yt_task_vm]

    # Weekly horizontal for non-YouTube platforms (not applicable)
    for platform in [Platform.TIKTOK, Platform.INSTAGRAM, Platform.SPOTIFY]:
        task_vm = AdminTaskViewModel(
            name=f"Weekly Horizontal ({platform.value})",
            last_run_label="Not applicable",
            hours_since=None,
            older_than_24h=False,
            source="never",
            applicable=False,
            warning_message="Weekly horizontal is only implemented for YouTube",
            last_status=None,
            last_error=None,
            action_label="Not applicable",
        )
        tasks.append(task_vm)

    return AdminTasksPanelViewModel(
        tasks=tuple(tasks),
        any_running=any(t.is_running for t in tasks),
    )


@dataclass(frozen=True)
class PublisherViewModel:
    """Presentation model for a single publisher card."""

    slug: str
    name: str
    icon_class: str
    enabled: bool
    oauth_configured: bool
    last_publish_label: str
    last_error: str | None
    card_class: str
    can_run_auth_check: bool = False
    auth_check_action_label: str | None = None
    auth_check_label: str | None = None
    auth_check_state: str | None = None
    auth_check_message: str | None = None


@dataclass(frozen=True)
class AdminPublishersViewModel:
    """Presentation model for the admin publishers section."""

    publishers: tuple[PublisherViewModel, ...]


@dataclass(frozen=True)
class DataSourceViewModel:
    """Presentation model for a single data source card."""

    slug: str
    name: str
    icon_class: str
    source_type: str
    is_configured: bool
    status_label: str
    status_state: str


@dataclass(frozen=True)
class AdminDataConnectorsViewModel:
    """Presentation model for the admin data connectors section."""

    connectors: tuple[DataSourceViewModel, ...]


def build_admin_publishers_view_model(
    *,
    state_reader: Any,
    release_store: Any,
    settings: Any,
    check_results: Mapping[str, IntegrationCheckResult] | None = None,
) -> AdminPublishersViewModel:
    """Build publishers section from DB state + release store + settings."""
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    publishers: list[PublisherViewModel] = []
    checks = dict(check_results or {})

    platform_configs = [
        {
            "slug": "youtube",
            "name": "YouTube",
            "icon_class": "fab fa-youtube",
            "configured": bool(settings.yt_client_secret_file),
        },
        {
            "slug": "tiktok",
            "name": "TikTok",
            "icon_class": "fab fa-tiktok",
            "configured": bool(settings.tiktok_cookies_file or settings.tiktok_user_openid),
        },
        {
            "slug": "instagram",
            "name": "Instagram",
            "icon_class": "fab fa-instagram",
            "configured": bool(settings.instagram_client_username and settings.instagram_client_password),
        },
        {
            "slug": "spotify",
            "name": "Spotify",
            "icon_class": "fab fa-spotify",
            "configured": bool(settings.spotify_client_id and settings.spotify_client_secret),
        },
    ]

    for cfg in platform_configs:
        slug = cfg["slug"]
        enabled = state_reader.is_enabled(slug)
        oauth_configured = cfg["configured"]
        check_result = checks.get(slug)

        latest_release = release_store.get_latest_release(platform=slug, release_kind="DAILY_VERTICAL")
        if latest_release and latest_release.published_at:
            ts = latest_release.published_at
            hours = (now.timestamp() - ts) / _SECONDS_PER_HOUR
            if hours < _HOURS_PER_DAY:
                last_label = build_time_label(ts)
            else:
                last_label = datetime.fromtimestamp(ts, tz=UTC).isoformat(timespec="minutes")
        else:
            last_label = "Never"

        if not oauth_configured and not enabled:
            card_class = "platform-card--inactive"
        elif not oauth_configured:
            card_class = "platform-card--needs-auth"
        elif not enabled:
            card_class = "platform-card--disabled"
        else:
            card_class = "platform-card--active"

        publishers.append(
            PublisherViewModel(
                slug=slug,
                name=cfg["name"],
                icon_class=cfg["icon_class"],
                enabled=enabled,
                oauth_configured=oauth_configured,
                last_publish_label=last_label,
                last_error=None,
                card_class=card_class,
                can_run_auth_check=slug == "instagram" and oauth_configured,
                auth_check_action_label="Check auth" if slug == "instagram" else None,
                auth_check_label=(
                    "VERIFIED"
                    if check_result and check_result.status == IntegrationCheckStatus.OK
                    else (
                        "ERROR"
                        if check_result and check_result.status == IntegrationCheckStatus.ERROR
                        else (
                            "NOT CONFIGURED"
                            if check_result and check_result.status == IntegrationCheckStatus.NOT_CONFIGURED
                            else None
                        )
                    )
                ),
                auth_check_state=(
                    "on"
                    if check_result and check_result.status == IntegrationCheckStatus.OK
                    else (
                        "off"
                        if check_result and check_result.status == IntegrationCheckStatus.ERROR
                        else (
                            "na"
                            if check_result and check_result.status == IntegrationCheckStatus.NOT_CONFIGURED
                            else None
                        )
                    )
                ),
                auth_check_message=check_result.message if check_result else None,
            )
        )

    return AdminPublishersViewModel(publishers=tuple(publishers))


def build_admin_data_connectors_view_model(
    *,
    settings: Any,
) -> AdminDataConnectorsViewModel:
    """Build data connectors section from settings."""
    connectors: list[DataSourceViewModel] = []

    if settings.yt_search_region_code:
        configured = bool(settings.yt_client_secret_file)
        connectors.append(
            DataSourceViewModel(
                slug="youtube",
                name="YouTube",
                icon_class="fab fa-youtube",
                source_type="videos",
                is_configured=configured,
                status_label="CONNECTED" if configured else "NOT CONFIGURED",
                status_state="on" if configured else "na",
            )
        )

    connectors.append(
        DataSourceViewModel(
            slug="themoviedb",
            name="TheMovieDB",
            icon_class="fas fa-film",
            source_type="movies",
            is_configured=False,
            status_label="COMING SOON",
            status_state="na",
        )
    )

    return AdminDataConnectorsViewModel(connectors=tuple(connectors))
