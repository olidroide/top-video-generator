"""Dependency factories for the FastAPI web layer."""

from pathlib import Path
from typing import Annotated, cast

from fastapi import Depends, Request

from src.application.authorize_use_case import AuthorizeUseCase
from src.application.check_platform_connection_use_case import CheckPlatformConnectionUseCase
from src.application.fetch_top_videos_use_case import FetchTopVideosUseCase
from src.application.get_admin_task_status_use_case import GetAdminTaskStatusUseCase
from src.application.get_operational_metrics_use_case import GetOperationalMetricsUseCase
from src.application.get_setup_page_use_case import GetSetupPageUseCase
from src.application.get_top_videos_dashboard_use_case import GetTopVideosDashboardUseCase
from src.application.trigger_admin_task_use_case import TriggerAdminTaskUseCase
from src.config.settings import AppSettings, get_app_settings
from src.domain.models import SpotifyAuth, YtAuth
from src.domain.ports import AuthCredentialStore as AuthenticationRepositoryPort
from src.domain.ports import IntegrationChecker, OAuthProvider
from src.domain.ports import OperationalMetricsReader as OperationalMetricsRepositoryPort
from src.domain.ports import ReleaseDateValidator as ReleaseRepositoryPort
from src.domain.ports import TimeSeriesReader as TimeSeriesRepositoryPort
from src.domain.ports import VideoMetadataReader as VideoRepositoryPort
from src.infrastructure.social.spotify_client import SpotifyClient
from src.infrastructure.storage.auth_repository import AuthenticationRepository as TinyDbAuthenticationRepository
from src.infrastructure.storage.operational_metrics_repository import (
    OperationalMetricsRepository as TinyFluxOperationalMetricsRepository,
)
from src.infrastructure.storage.release_repository import ReleaseRepository as TinyDbReleaseRepository
from src.infrastructure.storage.timeseries_repository import TimeSeriesRepository as TinyDbTimeSeriesRepository
from src.infrastructure.storage.video_repository import VideoRepository as TinyDbVideoRepository
from src.infrastructure.youtube.yt_client import YTClient
from src.infrastructure.youtube.yt_fake_client import YTClientFake


def get_yt_client(settings: AppSettings | None = None) -> OAuthProvider[YtAuth]:
    resolved_settings = settings if settings is not None else get_app_settings()
    return YTClient(resolved_settings) if resolved_settings.is_production_env else YTClientFake(resolved_settings)


def get_settings(request: Request) -> AppSettings:
    app_settings = getattr(request.app.state, "settings", None)
    if app_settings is not None:
        return cast("AppSettings", app_settings)
    return get_app_settings()


def get_yt_provider(
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> OAuthProvider[YtAuth]:
    return get_yt_client(settings)


def get_spotify_provider(
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> OAuthProvider[SpotifyAuth]:
    return SpotifyClient(settings)


def get_auth_repo(settings: Annotated[AppSettings, Depends(get_settings)]) -> AuthenticationRepositoryPort:
    return TinyDbAuthenticationRepository(Path(settings.db_auth_file))


def get_release_repo(settings: Annotated[AppSettings, Depends(get_settings)]) -> ReleaseRepositoryPort:
    return TinyDbReleaseRepository(settings.db_release_file)


def get_timeseries_repo(settings: Annotated[AppSettings, Depends(get_settings)]) -> TimeSeriesRepositoryPort:
    return TinyDbTimeSeriesRepository(settings.db_timeseries_file)


def get_video_repo(settings: Annotated[AppSettings, Depends(get_settings)]) -> VideoRepositoryPort:
    return TinyDbVideoRepository(Path(settings.db_video_file))


def get_operational_metrics_repo(
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> OperationalMetricsRepositoryPort:
    db_path = settings.db_timeseries_file if settings.is_production_env else f"{settings.db_timeseries_file}.test"
    return TinyFluxOperationalMetricsRepository(
        db_path,
        retention_days=settings.operational_metrics_retention_days,
    )


def get_authorize_use_case(
    auth_repo: Annotated[AuthenticationRepositoryPort, Depends(get_auth_repo)],
    yt_provider: Annotated[OAuthProvider[YtAuth], Depends(get_yt_provider)],
    spotify_provider: Annotated[OAuthProvider[SpotifyAuth], Depends(get_spotify_provider)],
) -> AuthorizeUseCase:
    return AuthorizeUseCase(
        auth_repo=auth_repo,
        yt_provider=yt_provider,
        spotify_provider=spotify_provider,
    )


def get_fetch_top_videos_use_case(
    timeseries_repo: Annotated[TimeSeriesRepositoryPort, Depends(get_timeseries_repo)],
    video_repo: Annotated[VideoRepositoryPort, Depends(get_video_repo)],
) -> FetchTopVideosUseCase:
    return FetchTopVideosUseCase(timeseries_repo, video_repo)


def get_top_videos_dashboard_use_case(
    fetch_top_videos_use_case: Annotated[FetchTopVideosUseCase, Depends(get_fetch_top_videos_use_case)],
    release_port: Annotated[ReleaseRepositoryPort, Depends(get_release_repo)],
) -> GetTopVideosDashboardUseCase:
    return GetTopVideosDashboardUseCase(fetch_videos=fetch_top_videos_use_case, release_port=release_port)


def get_setup_page_use_case(
    auth_repo: Annotated[AuthenticationRepositoryPort, Depends(get_auth_repo)],
    yt_provider: Annotated[OAuthProvider[YtAuth], Depends(get_yt_provider)],
    spotify_provider: Annotated[OAuthProvider[SpotifyAuth], Depends(get_spotify_provider)],
) -> GetSetupPageUseCase:
    return GetSetupPageUseCase(
        auth_repo=auth_repo,
        yt_provider=yt_provider,
        spotify_provider=spotify_provider,
    )


def get_integration_checkers() -> list[IntegrationChecker]:
    from src.infrastructure.integration_checker_registry import build_integration_checkers

    return build_integration_checkers()


def get_check_platform_connection_use_case(
    checkers: Annotated[list[IntegrationChecker], Depends(get_integration_checkers)],
) -> CheckPlatformConnectionUseCase:
    return CheckPlatformConnectionUseCase(checkers=checkers)


def get_admin_task_status_use_case(
    timeseries_repo: Annotated[TimeSeriesRepositoryPort, Depends(get_timeseries_repo)],
    release_repo: Annotated[ReleaseRepositoryPort, Depends(get_release_repo)],
) -> GetAdminTaskStatusUseCase:
    return GetAdminTaskStatusUseCase(timeseries_repo, release_repo)


def get_operational_metrics_use_case(
    metrics_repo: Annotated[OperationalMetricsRepositoryPort, Depends(get_operational_metrics_repo)],
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> GetOperationalMetricsUseCase:
    return GetOperationalMetricsUseCase(
        metrics_repo,
        window_hours=settings.operational_metrics_window_hours,
    )


def get_trigger_admin_task_use_case() -> TriggerAdminTaskUseCase:
    return TriggerAdminTaskUseCase()


AuthorizeUseCaseDep = Annotated[AuthorizeUseCase, Depends(get_authorize_use_case)]
AppSettingsDep = Annotated[AppSettings, Depends(get_settings)]
AuthenticationRepositoryDep = Annotated[AuthenticationRepositoryPort, Depends(get_auth_repo)]
FetchTopVideosUseCaseDep = Annotated[FetchTopVideosUseCase, Depends(get_fetch_top_videos_use_case)]
GetTopVideosDashboardUseCaseDep = Annotated[GetTopVideosDashboardUseCase, Depends(get_top_videos_dashboard_use_case)]
GetSetupPageUseCaseDep = Annotated[GetSetupPageUseCase, Depends(get_setup_page_use_case)]
CheckPlatformConnectionUseCaseDep = Annotated[
    CheckPlatformConnectionUseCase, Depends(get_check_platform_connection_use_case)
]
ReleaseRepositoryDep = Annotated[ReleaseRepositoryPort, Depends(get_release_repo)]
ReleaseReadPortDep = Annotated[ReleaseRepositoryPort, Depends(get_release_repo)]
SpotifyProviderDep = Annotated[OAuthProvider[SpotifyAuth], Depends(get_spotify_provider)]
YouTubeProviderDep = Annotated[OAuthProvider[YtAuth], Depends(get_yt_provider)]
TimeSeriesRepositoryDep = Annotated[TimeSeriesRepositoryPort, Depends(get_timeseries_repo)]
VideoRepositoryDep = Annotated[VideoRepositoryPort, Depends(get_video_repo)]
GetAdminTaskStatusUseCaseDep = Annotated[GetAdminTaskStatusUseCase, Depends(get_admin_task_status_use_case)]
TriggerAdminTaskUseCaseDep = Annotated[TriggerAdminTaskUseCase, Depends(get_trigger_admin_task_use_case)]
GetOperationalMetricsUseCaseDep = Annotated[
    GetOperationalMetricsUseCase,
    Depends(get_operational_metrics_use_case),
]
