from typing import Protocol, runtime_checkable
from .models import CanonicalVideo, PublishingResult, Platform

@runtime_checkable
class VideoDataSource(Protocol):
    async def fetch_top_videos(self, *, region: str, date: str | None = None) -> list[CanonicalVideo]:
        ...

@runtime_checkable
class VideoPublisher(Protocol):
    @property
    def platform_name(self) -> Platform: ...
    @property
    def is_enabled(self) -> bool: ...
    async def publish_video(
        self, video_list: list[CanonicalVideo], file_path: str,
        title: str, description: str,
    ) -> PublishingResult: ...
