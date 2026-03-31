"""Dependency factories for the FastAPI web layer."""

from pathlib import Path
from typing import Annotated

from fastapi import Depends

from src.application.authorize_use_case import AuthorizeUseCase
from src.application.fetch_top_videos_use_case import FetchTopVideosUseCase
from src.config.settings import get_app_settings
from src.infrastructure.social.spotify_client import SpotifyClient
from src.infrastructure.social.tiktok_client import TikTokClient
from src.infrastructure.storage.auth_repository import AuthenticationRepository
from src.infrastructure.storage.release_repository import ReleaseRepository
from src.infrastructure.storage.timeseries_repository import TimeSeriesRepository
from src.infrastructure.storage.video_repository import VideoRepository
from src.infrastructure.youtube import YTClient, get_yt_client


def get_yt_provider() -> YTClient:
    return get_yt_client()


def get_tiktok_provider() -> TikTokClient:
    return TikTokClient()


def get_spotify_provider() -> SpotifyClient:
    return SpotifyClient()


def get_auth_repo() -> AuthenticationRepository:
    return AuthenticationRepository(Path(get_app_settings().db_data_file))


def get_release_repo() -> ReleaseRepository:
    return ReleaseRepository(get_app_settings().db_data_file)


def get_timeseries_repo() -> TimeSeriesRepository:
    return TimeSeriesRepository(get_app_settings().db_timeseries_file)


def get_video_repo() -> VideoRepository:
    return VideoRepository(Path(get_app_settings().db_data_file))


def get_authorize_use_case(
    auth_repo: Annotated[AuthenticationRepository, Depends(get_auth_repo)],
    yt_provider: Annotated[YTClient, Depends(get_yt_provider)],
    tiktok_provider: Annotated[TikTokClient, Depends(get_tiktok_provider)],
    spotify_provider: Annotated[SpotifyClient, Depends(get_spotify_provider)],
) -> AuthorizeUseCase:
    return AuthorizeUseCase(
        auth_repo=auth_repo,
        yt_provider=yt_provider,
        tiktok_provider=tiktok_provider,
        spotify_provider=spotify_provider,
    )


def get_fetch_top_videos_use_case(
    timeseries_repo: Annotated[TimeSeriesRepository, Depends(get_timeseries_repo)],
    video_repo: Annotated[VideoRepository, Depends(get_video_repo)],
) -> FetchTopVideosUseCase:
    return FetchTopVideosUseCase(timeseries_repo, video_repo)


AuthorizeUseCaseDep = Annotated[AuthorizeUseCase, Depends(get_authorize_use_case)]
AuthenticationRepositoryDep = Annotated[AuthenticationRepository, Depends(get_auth_repo)]
FetchTopVideosUseCaseDep = Annotated[FetchTopVideosUseCase, Depends(get_fetch_top_videos_use_case)]
ReleaseRepositoryDep = Annotated[ReleaseRepository, Depends(get_release_repo)]
SpotifyProviderDep = Annotated[SpotifyClient, Depends(get_spotify_provider)]
TikTokProviderDep = Annotated[TikTokClient, Depends(get_tiktok_provider)]
YouTubeProviderDep = Annotated[YTClient, Depends(get_yt_provider)]
TimeSeriesRepositoryDep = Annotated[TimeSeriesRepository, Depends(get_timeseries_repo)]
VideoRepositoryDep = Annotated[VideoRepository, Depends(get_video_repo)]
