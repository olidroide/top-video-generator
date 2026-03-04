"""Tests de conformidad estructural con los Protocols del dominio.

Verifican que cada adapter implementa correctamente el Protocol correspondiente
sin instanciar la clase en import-time (a diferencia del anti-patrón assert isinstance).
"""

from unittest.mock import AsyncMock

from src.domain.ports import VideoDataSource, VideoPublisher


def test_youtube_source_implements_protocol() -> None:
    from src.adapters.youtube_source import YouTubeSource

    source = YouTubeSource.__new__(YouTubeSource)
    source.client = AsyncMock()
    assert isinstance(source, VideoDataSource)


def test_youtube_publisher_implements_protocol() -> None:
    from src.adapters.youtube_publisher import YouTubePublisher

    publisher = YouTubePublisher.__new__(YouTubePublisher)
    assert isinstance(publisher, VideoPublisher)


def test_instagram_publisher_implements_protocol() -> None:
    from src.adapters.instagram_publisher import InstagramPublisher

    publisher = InstagramPublisher.__new__(InstagramPublisher)
    assert isinstance(publisher, VideoPublisher)


def test_tiktok_publisher_implements_protocol() -> None:
    from src.adapters.tiktok_publisher import TikTokPublisher

    publisher = TikTokPublisher.__new__(TikTokPublisher)
    assert isinstance(publisher, VideoPublisher)
