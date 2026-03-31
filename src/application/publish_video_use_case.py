from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.domain.models import CanonicalVideo, PublishingResult
from src.shared.logging import get_logger

if TYPE_CHECKING:
    from src.domain.ports import VideoPublisher

logger = get_logger(__name__)


@dataclass(frozen=True)
class PublishVideoRequest:
    video_list: tuple[CanonicalVideo, ...]
    file_path: str
    title: str
    description: str


@dataclass(frozen=True)
class PublishVideoResult:
    results: tuple[PublishingResult, ...]

    @property
    def all_succeeded(self) -> bool:
        return all(r.success for r in self.results)

    @property
    def failed(self) -> tuple[PublishingResult, ...]:
        return tuple(r for r in self.results if not r.success)


class PublishVideoUseCase:
    def __init__(self, publishers: list[VideoPublisher]) -> None:
        self._publishers = publishers

    async def execute(self, request: PublishVideoRequest) -> PublishVideoResult:
        async def _publish_one(publisher: VideoPublisher) -> PublishingResult:
            try:
                return await publisher.publish_video(
                    video_list=request.video_list,
                    file_path=request.file_path,
                    title=request.title,
                    description=request.description,
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

        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(_publish_one(p)) for p in self._publishers]

        results = [t.result() for t in tasks]
        for result in results:
            if result.success:
                logger.info("publish.success", platform=result.platform, published_id=result.published_id)
            else:
                logger.error("publish.failed", platform=result.platform, error=result.error)

        return PublishVideoResult(results=tuple(results))
