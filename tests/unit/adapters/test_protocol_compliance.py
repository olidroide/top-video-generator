"""Tests de conformidad estructural con los Protocols del dominio.

Verifican que cada adapter implementa correctamente el Protocol correspondiente
sin instanciar la clase en import-time (a diferencia del anti-patrón assert isinstance).
"""

from unittest.mock import create_autospec

from src.domain.ports import VideoDataSource, VideoPublisher


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
