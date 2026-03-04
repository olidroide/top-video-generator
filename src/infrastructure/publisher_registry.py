import structlog

from src.adapters.instagram_publisher import InstagramPublisher
from src.adapters.tiktok_publisher import TikTokPublisher
from src.adapters.youtube_publisher import YouTubePublisher
from src.domain.ports import VideoPublisher


def build_publishers() -> list[VideoPublisher]:
    logger = structlog.get_logger()

    publishers: list[VideoPublisher] = [
        InstagramPublisher(),
        TikTokPublisher(),
        YouTubePublisher(),
    ]
    enabled = [p for p in publishers if p.is_enabled]
    skipped = [p for p in publishers if not p.is_enabled]
    logger.info("publishers.active", platforms=[p.platform_name for p in enabled])
    logger.info("publishers.skipped", platforms=[p.platform_name for p in skipped])
    return enabled
