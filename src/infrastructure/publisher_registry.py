from src.adapters.instagram_publisher import InstagramPublisher
from src.adapters.tiktok_publisher import TikTokPublisher
from src.adapters.youtube_publisher import YouTubePublisher
from src.domain.ports import VideoPublisher
from src.shared.logging import get_logger

logger = get_logger(__name__)


def build_publishers() -> list[VideoPublisher]:
    candidates: list[InstagramPublisher | TikTokPublisher | YouTubePublisher] = [
        InstagramPublisher(),
        TikTokPublisher(),
        YouTubePublisher(),
    ]
    publishers: list[VideoPublisher] = list(candidates)
    enabled = [p for p in publishers if p.is_enabled]
    skipped = [p for p in publishers if not p.is_enabled]
    logger.info("publishers.active", platforms=[p.platform_name for p in enabled])
    logger.info("publishers.skipped", platforms=[p.platform_name for p in skipped])
    return enabled
