from __future__ import annotations

from dataclasses import dataclass

from src.domain.models import CanonicalVideo
from src.domain.ports import VideoDataSource


@dataclass(frozen=True)
class FetchTrendingRequest:
    region: str
    limit: int = 50
    date: str | None = None


@dataclass(frozen=True)
class FetchTrendingResult:
    videos: tuple[CanonicalVideo, ...]
    region: str

    @property
    def fetched_count(self) -> int:
        return len(self.videos)


class FetchTrendingUseCase:
    def __init__(self, source: VideoDataSource) -> None:
        self._source = source

    async def execute(self, request: FetchTrendingRequest) -> FetchTrendingResult:
        videos = await self._source.fetch_trending_videos(
            region=request.region,
            date=request.date,
        )
        # Score-based sort only makes sense once scoring is applied.
        # Until db_client scoring logic is migrated, separate scored from unscored.
        scored = [v for v in videos if v.score > 0.0]
        unscored = [v for v in videos if v.score == 0.0]
        # Prefer scored if available, fallback to raw order for unscored
        ordered = (sorted(scored, key=lambda v: v.score, reverse=True) + unscored)[: request.limit]
        return FetchTrendingResult(
            videos=tuple(ordered),
            region=request.region,
        )
