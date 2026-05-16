from src.adapters.instagram_publisher import InstagramPublisher
from src.adapters.tiktok_publisher import TikTokPublisher
from src.adapters.youtube_publisher import YouTubePublisher
from src.domain.ports import PublisherStateReader, VideoPublisher
from src.shared.logging import get_logger

logger = get_logger(__name__)


def build_publishers(state_reader: PublisherStateReader | None = None) -> list[VideoPublisher]:
    publishers: list[VideoPublisher] = [
        InstagramPublisher(),
        YouTubePublisher(),
        TikTokPublisher(),
    ]
    enabled = []
    skipped = []
    for p in publishers:
        platform_key = p.platform_name.value.lower()
        settings_enabled = p.is_enabled
        admin_enabled = state_reader.is_enabled(platform_key) if state_reader else True
        if settings_enabled and admin_enabled:
            enabled.append(p)
        else:
            skipped.append(p)
    logger.info("publishers.active", platforms=[p.platform_name for p in enabled])
    logger.info("publishers.skipped", platforms=[p.platform_name for p in skipped])
    return enabled
