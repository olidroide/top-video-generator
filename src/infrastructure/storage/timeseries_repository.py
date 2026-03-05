"""Time-series data repository (TinyFlux backend)."""

from __future__ import annotations

from datetime import UTC, datetime

from tinyflux import Point, TagQuery, TimeQuery, TinyFlux

from src.domain.models import VideoPoint
from src.shared.logging import get_logger

logger = get_logger(__name__)


class TimeSeriesRepository:
    """
    Manages video time-series data (views, likes tracked over time).

    Storage: TinyFlux (CSV-based time-series database)
    Measurement: "Video visualizations"
    tags: video_id, score_status
    fields: views, likes, views_growth, score
    """

    _MEASUREMENT = "Video visualizations"

    def __init__(self, db_path: str) -> None:
        """Initialize repository with TinyFlux backend."""
        self._db = TinyFlux(db_path)

    def add_video_point(self, video_point: VideoPoint) -> None:
        """
        Insert a new video data point into time-series.

        Args:
            video_point: VideoPoint with video_id, views, likes, score, timestamp.
        """
        self._db.insert(
            Point(
                measurement=self._MEASUREMENT,
                time=video_point.time,
                tags={
                    "video_id": video_point.video_id,
                    "score_status": video_point.score_status.value if video_point.score_status else "UNKNOWN",
                },
                fields={
                    "views": video_point.views,
                    "likes": video_point.likes,
                    "views_growth": video_point.views_growth or 0,
                    "score": video_point.score or 0,
                },
            )
        )

    def update_video_point(self, video_point: VideoPoint) -> None:
        """
        Update an existing video data point.

        Args:
            video_point: Updated VideoPoint with matching video_id and timestamp.
        """
        query = (TagQuery().video_id == video_point.video_id) & (TimeQuery() == video_point.time.astimezone(UTC))
        self._db.update(
            query,
            tags={
                "score_status": video_point.score_status.value if video_point.score_status else "UNKNOWN",
            },
            fields={
                "views_growth": video_point.views_growth or 0,
                "score": video_point.score or 0,
            },
        )

    def get_all_points_by_video(self, video_id: str) -> list[Point]:
        """
        Retrieve all time-series points for a specific video.

        Args:
            video_id: YouTube video ID.

        Returns:
            List of Point objects from TinyFlux (raw).
        """
        query = TagQuery().video_id == video_id
        return self._db.search(query)

    def get_last_timestamp(self) -> datetime | None:
        """
        Get the most recent timestamp in the entire time-series database.

        Returns:
            datetime of the last recorded point, or None if empty.
        """
        # TinyFlux queries by time range; get all points and find max time
        all_points = self._db.all()
        if not all_points:
            return None
        # Points are ordered by time; get the latest
        return all_points[-1].time if all_points else None

    def close(self) -> None:
        """Close database connection."""
        self._db.close()
