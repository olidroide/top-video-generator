"""Time-series data repository (TinyFlux backend)."""

from __future__ import annotations

from datetime import UTC, datetime

from tinyflux import Point, TagQuery, TimeQuery, TinyFlux

from src.domain.models import VideoPoint, VideoScoreStatus
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
    _MIN_TIME = datetime(1970, 1, 1, tzinfo=UTC)

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
        return [point for point in self._db.search(query) if self._is_video_measurement(point)]

    def get_last_timestamp(self) -> datetime | None:
        """
        Get the most recent timestamp in the entire time-series database.

        Returns:
            datetime of the last recorded point, or None if empty.
        """
        points = self._db.search(TimeQuery() >= self._MIN_TIME, sorted=True)
        if not points:
            return None
        for point in reversed(points):
            if point.time is None or not self._is_video_measurement(point):
                continue
            return point.time.astimezone(UTC)
        return None

    def get_points_by_date_range(self, start_time: datetime, end_time: datetime) -> list[Point]:
        """
        Retrieve all points within a time range.

        Args:
            start_time: Start of time range (exclusive).
            end_time: End of time range (exclusive).

        Returns:
            List of Point objects matching the time range.
        """
        start_utc = start_time.astimezone(UTC)
        end_utc = end_time.astimezone(UTC)
        query = (TimeQuery() > start_utc) & (TimeQuery() < end_utc)
        return [point for point in self._db.search(query) if self._is_video_measurement(point)]

    def _is_video_measurement(self, point: Point) -> bool:
        """Check whether a TinyFlux point belongs to video timeseries."""
        return point.measurement == self._MEASUREMENT

    def get_video_points_by_date_range(self, start_time: datetime, end_time: datetime) -> list[VideoPoint]:
        """Retrieve points within a time range, mapped to VideoPoint models."""
        return [self._map_point(p) for p in self.get_points_by_date_range(start_time, end_time)]

    @staticmethod
    def _map_point(point: Point) -> VideoPoint:
        """Convert a raw TinyFlux Point to a VideoPoint model."""
        raw_status = point.tags.get("score_status")
        point_time = TimeSeriesRepository._require_point_time(point)
        return VideoPoint(
            time=point_time,
            video_id=point.tags.get("video_id") or "",
            views=TimeSeriesRepository._int_field(point, "views"),
            likes=TimeSeriesRepository._int_field(point, "likes"),
            views_growth=TimeSeriesRepository._optional_int_field(point, "views_growth"),
            score=TimeSeriesRepository._optional_int_field(point, "score"),
            score_status=VideoScoreStatus(raw_status) if raw_status else None,
        )

    @staticmethod
    def _require_point_time(point: Point) -> datetime:
        """Return a point timestamp normalized to UTC."""
        if point.time is None:
            msg = "TinyFlux point is missing time"
            raise ValueError(msg)
        return point.time.astimezone(UTC)

    @staticmethod
    def _int_field(point: Point, field_name: str) -> int:
        """Read a numeric TinyFlux field as an int with 0 as fallback."""
        raw_value = point.fields.get(field_name, 0)
        if raw_value is None:
            return 0
        return int(raw_value)

    @staticmethod
    def _optional_int_field(point: Point, field_name: str) -> int | None:
        """Read an optional numeric TinyFlux field as an int or None."""
        raw_value = point.fields.get(field_name, 0)
        if raw_value in (None, 0):
            return None
        return int(raw_value)

    def close(self) -> None:
        """Close database connection."""
        self._db.close()
