"""Video metadata repository backed by TinyDB."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from pydantic import BaseModel
from tinydb import Query, TinyDB

from src.domain.models import CanonicalVideo

if TYPE_CHECKING:
    from pathlib import Path


class VideoRecord(BaseModel):
    """
    Infrastructure-layer persistence model (NOT a domain entity).

    Bridges the gap between CanonicalVideo (domain) and TinyDB storage.
    """

    video_id: str
    title: str = ""
    channel_name: str = ""
    views: int = 0
    likes: int = 0
    description: str = ""
    duration_seconds: float = 0.0

    @classmethod
    def from_canonical(cls, video: CanonicalVideo) -> VideoRecord:
        """Convert domain entity → infrastructure entity."""
        return cls(
            video_id=video.video_id,
            title=video.title,
            channel_name=video.channel_name,
            views=video.views,
            likes=video.likes,
            description=video.description,
            duration_seconds=video.duration_seconds,
        )

    def to_canonical(self) -> CanonicalVideo:
        """Convert infrastructure entity → domain entity."""
        return CanonicalVideo(
            video_id=self.video_id,
            title=self.title,
            channel_name=self.channel_name,
            views=self.views,
            likes=self.likes,
            description=self.description,
            duration_seconds=self.duration_seconds,
        )


class VideoRepository:
    """
    Video metadata repository using TinyDB.

    Responsibility: Persist and retrieve video metadata (title, channel, views, etc).
    Does NOT handle time-series data (views over time) — use TimeSeriesRepository for that.
    """

    _TABLE = "video"

    def __init__(self, db_path: Path) -> None:
        """
        Initialize repository.

        Args:
            db_path: Path to TinyDB file (e.g., /path/to/db.json).
        """
        self._db = TinyDB(str(db_path))
        self._table = self._db.table(self._TABLE)

    def upsert(self, video: CanonicalVideo) -> None:
        """
        Insert or update a video record.

        Args:
            video: Domain entity to persist.
        """
        record = VideoRecord.from_canonical(video).model_dump()
        self._table.upsert(record, Query().video_id == video.video_id)

    def get(self, video_id: str) -> CanonicalVideo | None:
        """
        Retrieve a video by ID.

        Args:
            video_id: YouTube video ID.

        Returns:
            CanonicalVideo if found, None otherwise.
        """
        results = self._table.search(Query().video_id == video_id)
        if not results:
            return None
        return VideoRecord.model_validate(results[0]).to_canonical()

    def search(self, pattern: str) -> list[CanonicalVideo]:
        """
        Search videos by pattern (case-insensitive regex).

        Args:
            pattern: Regex pattern (e.g., "song.*title").

        Returns:
            List of matching CanonicalVideo entities.
        """
        results = self._table.search(Query().video_id.matches(pattern, flags=re.IGNORECASE))
        return [VideoRecord.model_validate(r).to_canonical() for r in results]

    def delete(self, video_id: str) -> int:
        """
        Delete a video by ID.

        Args:
            video_id: YouTube video ID.

        Returns:
            Number of records deleted (0 or 1).
        """
        return len(self._table.remove(Query().video_id == video_id))

    def all(self) -> list[CanonicalVideo]:
        """
        Retrieve all videos.

        Returns:
            List of all CanonicalVideo entities in storage.
        """
        return [VideoRecord.model_validate(r).to_canonical() for r in self._table.all()]

    def clear(self) -> None:
        """Delete all videos from table (use with caution)."""
        self._table.truncate()

    def close(self) -> None:
        """Close database connection."""
        self._db.close()
