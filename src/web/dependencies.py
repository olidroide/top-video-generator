"""Dependency factories for the FastAPI web layer."""

from pathlib import Path
from typing import Annotated, cast

from fastapi import Depends, Request

from src.application.authorize_use_case import AuthorizeUseCase
from src.application.fetch_top_videos_use_case import FetchTopVideosUseCase
from src.application.get_setup_page_use_case import GetSetupPageUseCase
from src.application.get_top_videos_dashboard_use_case import GetTopVideosDashboardUseCase
from src.config.settings import AppSettings, get_app_settings
from src.domain.models import SpotifyAuth, TikTokAuth, YtAuth
from src.domain.ports import (
    AuthCredentialStore as AuthenticationRepositoryPort,
)
from src.domain.ports import OAuthProvider
from src.domain.ports import (
    ReleaseDateValidator as ReleaseRepositoryPort,
)
from src.domain.ports import (
    TimeSeriesReader as TimeSeriesRepositoryPort,
)
from src.domain.ports import (
    VideoMetadataReader as VideoRepositoryPort,
)
from src.infrastructure.social.spotify_client import SpotifyClient
from src.infrastructure.social.tiktok_client import TikTokClient
from src.infrastructure.storage.auth_repository import AuthenticationRepository as TinyDbAuthenticationRepository
from src.infrastructure.storage.release_repository import ReleaseRepository as TinyDbReleaseRepository
from src.infrastructure.storage.timeseries_repository import TimeSeriesRepository as TinyDbTimeSeriesRepository
from src.infrastructure.storage.video_repository import VideoRepository as TinyDbVideoRepository
from src.infrastructure.youtube.yt_client import YTClient
from src.infrastructure.youtube.yt_fake_client import YTClientFake


def get_yt_client() -> OAuthProvider[YtAuth]:
    settings = get_app_settings()
    return YTClient() if settings.is_production_env else YTClientFake()


def get_yt_provider() -> OAuthProvider[YtAuth]:
    return get_yt_client()


def get_tiktok_provider() -> OAuthProvider[TikTokAuth]:
    return TikTokClient()


def get_spotify_provider() -> OAuthProvider[SpotifyAuth]:
    return SpotifyClient()


def get_settings(request: Request) -> AppSettings:
    app_settings = getattr(request.app.state, "settings", None)
    if app_settings is not None:
        return cast("AppSettings", app_settings)
    return get_app_settings()


def get_auth_repo(settings: Annotated[AppSettings, Depends(get_settings)]) -> AuthenticationRepositoryPort:
    return TinyDbAuthenticationRepository(Path(settings.db_data_file))


def get_release_repo(settings: Annotated[AppSettings, Depends(get_settings)]) -> ReleaseRepositoryPort:
    return TinyDbReleaseRepository(settings.db_data_file)


def get_timeseries_repo(settings: Annotated[AppSettings, Depends(get_settings)]) -> TimeSeriesRepositoryPort:
    return TinyDbTimeSeriesRepository(settings.db_timeseries_file)


def get_video_repo(settings: Annotated[AppSettings, Depends(get_settings)]) -> VideoRepositoryPort:
    return TinyDbVideoRepository(Path(settings.db_data_file))


def get_authorize_use_case(
    auth_repo: Annotated[AuthenticationRepositoryPort, Depends(get_auth_repo)],
    yt_provider: Annotated[OAuthProvider[YtAuth], Depends(get_yt_provider)],
    tiktok_provider: Annotated[OAuthProvider[TikTokAuth], Depends(get_tiktok_provider)],
    spotify_provider: Annotated[OAuthProvider[SpotifyAuth], Depends(get_spotify_provider)],
) -> AuthorizeUseCase:
    return AuthorizeUseCase(
        auth_repo=auth_repo,
        yt_provider=yt_provider,
        tiktok_provider=tiktok_provider,
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
    tiktok_provider: Annotated[OAuthProvider[TikTokAuth], Depends(get_tiktok_provider)],
    spotify_provider: Annotated[OAuthProvider[SpotifyAuth], Depends(get_spotify_provider)],
) -> GetSetupPageUseCase:
    return GetSetupPageUseCase(
        auth_repo=auth_repo,
        yt_provider=yt_provider,
        tiktok_provider=tiktok_provider,
        spotify_provider=spotify_provider,
    )


AuthorizeUseCaseDep = Annotated[AuthorizeUseCase, Depends(get_authorize_use_case)]
AppSettingsDep = Annotated[AppSettings, Depends(get_settings)]
AuthenticationRepositoryDep = Annotated[AuthenticationRepositoryPort, Depends(get_auth_repo)]
FetchTopVideosUseCaseDep = Annotated[FetchTopVideosUseCase, Depends(get_fetch_top_videos_use_case)]
GetTopVideosDashboardUseCaseDep = Annotated[GetTopVideosDashboardUseCase, Depends(get_top_videos_dashboard_use_case)]
GetSetupPageUseCaseDep = Annotated[GetSetupPageUseCase, Depends(get_setup_page_use_case)]
ReleaseRepositoryDep = Annotated[ReleaseRepositoryPort, Depends(get_release_repo)]
ReleaseReadPortDep = Annotated[ReleaseRepositoryPort, Depends(get_release_repo)]
SpotifyProviderDep = Annotated[OAuthProvider[SpotifyAuth], Depends(get_spotify_provider)]
TikTokProviderDep = Annotated[OAuthProvider[TikTokAuth], Depends(get_tiktok_provider)]
YouTubeProviderDep = Annotated[OAuthProvider[YtAuth], Depends(get_yt_provider)]
TimeSeriesRepositoryDep = Annotated[TimeSeriesRepositoryPort, Depends(get_timeseries_repo)]
VideoRepositoryDep = Annotated[VideoRepositoryPort, Depends(get_video_repo)]
