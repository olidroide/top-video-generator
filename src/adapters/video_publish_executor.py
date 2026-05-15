"""Adapter for executing per-platform video publication."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.domain.models import PublishingResult
from src.domain.ports import VideoPublishExecutor
from src.shared.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

    from src.domain.models import CanonicalVideo
    from src.domain.ports import VideoPublisher

logger = get_logger(__name__)


class VideoPublishExecutorAdapter(VideoPublishExecutor):
    """Execute publication for one publisher with resilient error handling."""

    async def publish(
        self,
        publisher: VideoPublisher,
        video_list: Sequence[CanonicalVideo],
        file_path: str,
        title: str,
        description: str,
    ) -> PublishingResult:
        try:
            return await publisher.publish_video(
                video_list=video_list,
                file_path=file_path,
                title=title,
                description=description,
            )
        except Exception as exc:
            logger.exception(
                "publish.unexpected_error",
                platform=publisher.platform_name,
                error=str(exc),
            )
            return PublishingResult(
                platform=publisher.platform_name,
                success=False,
                error=str(exc),
            )
