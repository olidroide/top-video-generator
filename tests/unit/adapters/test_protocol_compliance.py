"""Structural compliance tests for domain Protocols.

These tests verify that each concrete adapter or repository satisfies the
corresponding Protocol using static type assertions instead of runtime
`isinstance` checks.
"""

from typing import assert_type
from unittest.mock import create_autospec

from src.domain.models import TikTokAuth, YtAuth
from src.domain.ports import (
    AuthCredentialStore,
    IntegrationChecker,
    OAuthProvider,
    ReleaseDateValidator,
    ReleaseStore,
    TimeSeriesReader,
    TrendingVideoFetcher,
    VerticalVideoPipeline,
    VideoMetadataReader,
    VideoPublisher,
    VideoPublishExecutor,
)


def test_youtube_source_implements_protocol() -> None:
    from src.adapters.youtube_source import YouTubeSource
    from src.infrastructure.youtube.yt_client import YTClient

    client: YTClient = create_autospec(YTClient, instance=True)
    source: YouTubeSource = YouTubeSource(client=client)
    assert_type(source, TrendingVideoFetcher)


def test_youtube_publisher_implements_protocol() -> None:
    from src.adapters.youtube_publisher import YouTubePublisher

    publisher: YouTubePublisher = create_autospec(YouTubePublisher, instance=True)
    assert_type(publisher, VideoPublisher)


def test_instagram_publisher_implements_protocol() -> None:
    from src.adapters.instagram_publisher import InstagramPublisher

    publisher: InstagramPublisher = create_autospec(InstagramPublisher, instance=True)
    assert_type(publisher, VideoPublisher)


def test_tiktok_publisher_implements_protocol() -> None:
    from src.adapters.tiktok_publisher import TikTokPublisher

    publisher: TikTokPublisher = create_autospec(TikTokPublisher, instance=True)
    assert_type(publisher, VideoPublisher)


def test_youtube_integration_checker_implements_protocol() -> None:
    from src.adapters.youtube_integration_checker import YouTubeIntegrationChecker

    checker: YouTubeIntegrationChecker = create_autospec(YouTubeIntegrationChecker, instance=True)
    assert_type(checker, IntegrationChecker)


def test_tiktok_integration_checker_implements_protocol() -> None:
    from src.adapters.tiktok_integration_checker import TikTokIntegrationChecker

    checker: TikTokIntegrationChecker = create_autospec(TikTokIntegrationChecker, instance=True)
    assert_type(checker, IntegrationChecker)


def test_instagram_integration_checker_implements_protocol() -> None:
    from src.adapters.instagram_integration_checker import InstagramIntegrationChecker

    checker: InstagramIntegrationChecker = create_autospec(InstagramIntegrationChecker, instance=True)
    assert_type(checker, IntegrationChecker)


def test_yt_client_implements_oauth_provider() -> None:
    from src.infrastructure.youtube.yt_client import YTClient

    client: YTClient = create_autospec(YTClient, instance=True)
    assert_type(client, OAuthProvider[YtAuth])


def test_tiktok_client_implements_oauth_provider() -> None:
    from src.infrastructure.social.tiktok_client import TikTokClient

    client: TikTokClient = create_autospec(TikTokClient, instance=True)
    assert_type(client, OAuthProvider[TikTokAuth])


def test_auth_repository_implements_protocol() -> None:
    from src.infrastructure.storage.auth_repository import AuthenticationRepository as TinyDbAuthenticationRepository

    auth_repo: TinyDbAuthenticationRepository = create_autospec(TinyDbAuthenticationRepository, instance=True)
    assert_type(auth_repo, AuthCredentialStore)


def test_release_repository_implements_protocol() -> None:
    from src.infrastructure.storage.release_repository import ReleaseRepository as TinyDbReleaseRepository

    release_repo: TinyDbReleaseRepository = create_autospec(TinyDbReleaseRepository, instance=True)
    assert_type(release_repo, ReleaseDateValidator)
    assert_type(release_repo, ReleaseStore)


def test_vertical_video_pipeline_adapter_implements_protocol() -> None:
    from src.adapters.vertical_video_pipeline import VerticalVideoPipelineAdapter

    adapter: VerticalVideoPipelineAdapter = create_autospec(VerticalVideoPipelineAdapter, instance=True)
    assert_type(adapter, VerticalVideoPipeline)


def test_video_publish_executor_adapter_implements_protocol() -> None:
    from src.adapters.video_publish_executor import VideoPublishExecutorAdapter

    adapter: VideoPublishExecutorAdapter = create_autospec(VideoPublishExecutorAdapter, instance=True)
    assert_type(adapter, VideoPublishExecutor)


def test_timeseries_repository_implements_protocol() -> None:
    from src.infrastructure.storage.timeseries_repository import TimeSeriesRepository as TinyDbTimeSeriesRepository

    timeseries_repo: TinyDbTimeSeriesRepository = create_autospec(TinyDbTimeSeriesRepository, instance=True)
    assert_type(timeseries_repo, TimeSeriesReader)


def test_video_repository_implements_protocol() -> None:
    from src.infrastructure.storage.video_repository import VideoRepository as TinyDbVideoRepository

    video_repo: TinyDbVideoRepository = create_autospec(TinyDbVideoRepository, instance=True)
    assert_type(video_repo, VideoMetadataReader)
