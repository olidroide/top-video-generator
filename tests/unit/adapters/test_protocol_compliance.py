"""Tests de conformidad estructural con los Protocols del dominio.

Verifican que cada adapter implementa correctamente el Protocol correspondiente
sin instanciar la clase en import-time (a diferencia del anti-patrón assert isinstance).
"""

from unittest.mock import create_autospec

from src.domain.ports import (
    SpotifyOAuthProvider,
    TikTokOAuthProvider,
    VideoDataSource,
    VideoPublisher,
    YouTubeOAuthProvider,
)


def test_youtube_source_implements_protocol() -> None:
    from src.adapters.youtube_source import YouTubeSource

    mock = create_autospec(YouTubeSource, instance=True)
    assert isinstance(mock, VideoDataSource)


def test_youtube_publisher_implements_protocol() -> None:
    from src.adapters.youtube_publisher import YouTubePublisher

    mock = create_autospec(YouTubePublisher, instance=True)
    assert isinstance(mock, VideoPublisher)


def test_instagram_publisher_implements_protocol() -> None:
    from src.adapters.instagram_publisher import InstagramPublisher

    mock = create_autospec(InstagramPublisher, instance=True)
    assert isinstance(mock, VideoPublisher)


def test_tiktok_publisher_implements_protocol() -> None:
    from src.adapters.tiktok_publisher import TikTokPublisher

    mock = create_autospec(TikTokPublisher, instance=True)
    assert isinstance(mock, VideoPublisher)


def test_yt_client_implements_youtube_oauth_provider() -> None:
    from src.infrastructure.youtube.client import YTClient

    mock = create_autospec(YTClient, instance=True)
    assert isinstance(mock, YouTubeOAuthProvider)


def test_tiktok_client_implements_tiktok_oauth_provider() -> None:
    from src.infrastructure.social.tiktok_client import TikTokClient

    mock = create_autospec(TikTokClient, instance=True)
    assert isinstance(mock, TikTokOAuthProvider)


def test_spotify_client_implements_spotify_oauth_provider() -> None:
    from src.infrastructure.social.spotify_client import SpotifyClient

    mock = create_autospec(SpotifyClient, instance=True)
    assert isinstance(mock, SpotifyOAuthProvider)
