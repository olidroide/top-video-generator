from src.adapters.instagram_integration_checker import InstagramIntegrationChecker
from src.adapters.tiktok_integration_checker import TikTokIntegrationChecker
from src.adapters.youtube_integration_checker import YouTubeIntegrationChecker
from src.domain.ports import IntegrationChecker
from src.shared.logging import get_logger

logger = get_logger(__name__)


def build_integration_checkers() -> list[IntegrationChecker]:
    checkers: list[IntegrationChecker] = [
        InstagramIntegrationChecker(),
        TikTokIntegrationChecker(),
        YouTubeIntegrationChecker(),
    ]
    logger.info(
        "integration_checkers.loaded",
        platforms=[checker.platform_name for checker in checkers],
    )
    return checkers
