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
    videos: list[CanonicalVideo]
    region: str
    fetched_count: int


class FetchTrendingUseCase:
    def __init__(self, source: VideoDataSource) -> None:
        self._source = source

    async def execute(self, request: FetchTrendingRequest) -> FetchTrendingResult:
        videos = await self._source.fetch_trending_videos(
            region=request.region,
            date=request.date,
        )
        top = sorted(videos, key=lambda v: v.score, reverse=True)[: request.limit]
        return FetchTrendingResult(
            videos=top,
            region=request.region,
            fetched_count=len(top),
        )
