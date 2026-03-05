"""
Database client orchestrator (Refactored for Phase 4).

DEPENDENCY STRUCTURE:
- Uses models from src.domain.models (Video, VideoPoint, Release, Auth*)
- Delegates to src.infrastructure.storage repositories (auth, timeseries, release)
- Maintains backward compatibility via re-exports

ONGOING REFACTORING:
- Scoring logic being moved to src.domain.services.scoring_service
- Eventually: DatabaseClient → thin facade, domain logic → pure functions
"""

import warnings
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

from pydantic import PastDate
from tinydb import Query, TinyDB
from tinyflux import Point, TagQuery, TimeQuery, TinyFlux

from src.config.settings import get_app_settings
from src.domain.models import (
    Channel,
    Release,
    SpotifyAuth,
    TikTokAuth,
    TimeseriesRange,
    TimePoint,
    Video,
    VideoPoint,
    VideoScoreStatus,
    YtAuth,
)
from src.infrastructure.storage.auth_repository import AuthenticationRepository
from src.infrastructure.storage.release_repository import ReleaseRepository
from src.infrastructure.storage.timeseries_repository import TimeSeriesRepository
from src.shared.logging import get_logger

logger = get_logger(__name__)

# ============================================================================
# Re-exports for backward compatibility
# ============================================================================

__all__ = [
    "DatabaseClient",
    "Video",
    "VideoPoint",
    "VideoScoreStatus",
    "Release",
    "SpotifyAuth",
    "TikTokAuth",
    "YtAuth",
    "Channel",
    "TimeseriesRange",
    "TimePoint",
    "video_list_mapper_hashtags",
    # Deprecated (use domain models instead)
    "ReleasePlatform",
    "VideoPointTools",
]


class ReleasePlatform:
    """
    DEPRECATED: Use models.ReleasePlatform (StrEnum) instead.

    Kept for backward compatibility with existing code.
    """

    YT = "YT"
    TIKTOK = "TIKTOK"
    SPOTIFY = "SPOTIFY"
    INSTAGRAM = "INSTAGRAM"


class VideoPointTools:
    """
    DEPRECATED: Scoring logic moved to src.domain.services.scoring_service.

    This class is kept for backward compatibility only.
    New code should use scoring_service.score_and_rank() instead.
    """

    @staticmethod
    def calculate_view_growth(last_video: VideoPoint, previous_video: VideoPoint | None) -> int:
        """Calculate absolute view growth between two points."""
        warnings.warn(
            "VideoPointTools.calculate_view_growth is deprecated; use scoring_service",
            DeprecationWarning,
            stacklevel=2,
        )
        if not previous_video:
            return last_video.views
        return abs(last_video.views - previous_video.views)

    @staticmethod
    def map_score_video_score_status(current_score=None, previous_score=None) -> VideoScoreStatus:
        """Map score delta to VideoScoreStatus (UP, DOWN, NEW, EQUAL)."""
        warnings.warn(
            "VideoPointTools.map_score_video_score_status is deprecated; use scoring_service",
            DeprecationWarning,
            stacklevel=2,
        )
        if not previous_score:
            return VideoScoreStatus.NEW
        if current_score == previous_score:
            return VideoScoreStatus.EQUAL
        if current_score < previous_score:
            return VideoScoreStatus.UP
        return VideoScoreStatus.DOWN

    @staticmethod
    def calculate_datetime_for_range(
        timeseries_range: TimeseriesRange,
        day: PastDate | None = None,
    ) -> datetime:
        """Calculate start datetime for a time range (DAILY=1d, WEEKLY=7d)."""
        warnings.warn(
            "VideoPointTools.calculate_datetime_for_range is deprecated",
            DeprecationWarning,
            stacklevel=2,
        )
        map_range_days = {TimeseriesRange.DAILY: 1, TimeseriesRange.WEEKLY: 7}
        if day is None:
            day = date.today()
        from_days_ago = map_range_days.get(timeseries_range, 7)
        from_datetime = datetime.combine(day, datetime.min.time())
        return from_datetime - timedelta(days=from_days_ago)

    @staticmethod
    def generate_top_list_compared(
        current_video_list: list[VideoPoint],
        previous_video_list: list[VideoPoint],
    ) -> list[VideoPoint]:
        """Rank current videos by growth, compare with previous state."""
        warnings.warn(
            "VideoPointTools.generate_top_list_compared is deprecated; use scoring_service",
            DeprecationWarning,
            stacklevel=2,
        )
        previous_map = {v.video_id: v for v in previous_video_list}

        # Calculate growth
        for video_point in current_video_list:
            prev = previous_map.get(video_point.video_id)
            if prev:
                video_point.views_growth = abs(video_point.views - prev.views)
            else:
                video_point.views_growth = video_point.views_growth or video_point.views

        # Sort by growth DESC
        current_video_list.sort(key=lambda x: x.views_growth or 0, reverse=True)

        # Assign ranks and status
        for rank, video_point in enumerate(current_video_list, start=1):
            prev = previous_map.get(video_point.video_id)
            prev_score = float(prev.score) if prev and prev.score else None
            video_point.score = rank
            video_point.score_previous = prev_score

            # Status
            if not prev_score:
                video_point.score_status = VideoScoreStatus.NEW
            elif video_point.score == prev_score:
                video_point.score_status = VideoScoreStatus.EQUAL
            elif video_point.score > prev_score:
                video_point.score_status = VideoScoreStatus.DOWN
            else:
                video_point.score_status = VideoScoreStatus.UP

        return current_video_list


class DatabaseClient:
    """
    Database client orchestrator.

    Responsibility:
    1. Orchestrate storage operations across multiple repositories
    2. Provide high-level queries (e.g., get_top_25_videos)
    3. Maintain backward compatibility during Phase 4 refactoring

    Delegation:
    - AuthenticationRepository: OAuth2 tokens (Spotify, TikTok, YouTube)
    - TimeSeriesRepository: VideoPoint timeseries (TinyFlux)
    - ReleaseRepository: Release tracking (TinyDB)
    - Raw TinyDB: Video metadata (direct access)
    """

    def __init__(self) -> None:
        """Initialize all repositories and database connections."""
        settings = get_app_settings()
        db_timeseries_file = settings.db_timeseries_file
        db_data_file = settings.db_data_file

        # Use test databases if not production
        if not settings.is_production_env:
            db_timeseries_file += ".test"
            db_data_file += ".test"

        # Initialize specialized repositories
        self._auth_repo = AuthenticationRepository(Path(db_data_file))
        self._timeseries_repo = TimeSeriesRepository(db_timeseries_file)
        self._release_repo = ReleaseRepository(db_data_file)

        # Direct database access for video metadata and complex queries
        self._tiny_db = TinyDB(db_data_file)
        self._db = TinyFlux(db_timeseries_file)

    # ========================================================================
    # Video Metadata Operations (TinyDB)
    # ========================================================================

    def add_or_update_video(self, video: Video) -> Video:
        """Insert or update video metadata (upsert)."""
        if self.get_video(video.video_id):
            return self.update_video(video)
        table = self._tiny_db.table("video")
        table.insert(video.model_dump())
        return video

    def update_video(self, video: Video) -> Video | None:
        """Update existing video metadata."""
        table = self._tiny_db.table("video")
        table.update(video.model_dump(), Query().video_id == video.video_id)
        return video

    def get_video(self, video_id: str) -> Video | None:
        """Retrieve video metadata by video ID."""
        table = self._tiny_db.table("video")
        results = table.search(Query().video_id == video_id)
        if not results:
            return None
        return Video.model_validate(results[0])

    def search_video(self, video_id: str | None = None) -> list[Video]:
        """Search videos by video_id pattern (regex, case-insensitive)."""
        table = self._tiny_db.table("video")
        if not video_id:
            return [Video.model_validate(r) for r in table.all()]
        results = table.search(Query().video_id.matches(video_id, flags=2))
        return [Video.model_validate(r) for r in results]

    # ========================================================================
    # Timeseries Operations (TinyFlux) - delegated to TimeSeriesRepository
    # ========================================================================

    def add_video_point(self, video_point: VideoPoint) -> None:
        """Insert video data point into time-series."""
        self._timeseries_repo.add_video_point(video_point)

    def update_video_point(self, video_point: VideoPoint) -> None:
        """Update existing video data point in time-series."""
        self._timeseries_repo.update_video_point(video_point)

    def get_all_points_by_video(
        self,
        video_id: list[str] | int | None = None,
        datetime_filter: datetime | None = None,
    ) -> Iterator[list[VideoPoint]]:
        """Iterate all time-series points for video(s), optionally filtered by date."""
        timequery = None
        if datetime_filter:
            from_dt = datetime_filter.astimezone(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            until_dt = from_dt.replace(hour=23, minute=59, second=59, microsecond=0)
            timequery = (TimeQuery() > from_dt) & (TimeQuery() < until_dt)

        # Get all unique video IDs if not specified
        if not video_id:
            video_id_list = list(set(self._db.get_tag_values().get("video_id", [])))
        elif isinstance(video_id, int):
            video_id_list = [str(video_id)]
        else:
            video_id_list = video_id if isinstance(video_id, list) else [video_id]

        video_id_list.sort()

        # Fetch and yield points per video
        for vid in video_id_list:
            query = TagQuery().video_id == vid
            if timequery:
                query = query & timequery
            points = self._db.search(query=query)
            if points:
                yield [self._map_point_video_point(point) for point in points]

    def get_last_timeseries_datetime(self) -> datetime | None:
        """Get the timestamp of the most recent data point in timeseries."""
        timestamps = list(set(self._db.get_timestamps()))
        if not timestamps:
            return None
        timestamps.sort(reverse=True)
        return timestamps[0].astimezone(timezone.utc)

    def get_last_timeseries_videos(self) -> Iterator[VideoPoint]:
        """Iterate all videos from the last recorded timestamp."""
        last_dt = self.get_last_timeseries_datetime()
        if not last_dt:
            return
        for point in self._db.search(TimeQuery() == last_dt):
            yield self._map_and_enrich(point)

    def get_today_timeseries_videos(self) -> Iterator[VideoPoint]:
        """Iterate all videos from today's timeseries data."""
        from_dt = datetime.combine(date.today(), datetime.min.time())
        for point in self._db.search(TimeQuery() > from_dt):
            yield self._map_and_enrich(point)

    def get_defined_range_timeseries_videos(
        self,
        timeseries_range: TimeseriesRange,
        day: PastDate | None = None,
    ) -> Iterator[VideoPoint]:
        """Iterate videos from a specific date range (DAILY or WEEKLY)."""
        if day is None:
            day = date.today()
        from_dt = VideoPointTools.calculate_datetime_for_range(timeseries_range, day)
        until_dt = from_dt + timedelta(days=1)
        timequery = (TimeQuery() > from_dt) & (TimeQuery() < until_dt)
        for point in self._db.search(timequery):
            yield self._map_and_enrich(point)

    # ========================================================================
    # Authentication Operations - delegated to AuthenticationRepository
    # ========================================================================

    def get_spotify_auth(self, client_id: str) -> SpotifyAuth | None:
        """Retrieve Spotify OAuth2 credentials."""
        return self._auth_repo.get_spotify_auth(client_id)

    def update_spotify_auth(self, spotify_auth: SpotifyAuth) -> SpotifyAuth | None:
        """Update Spotify OAuth2 credentials."""
        return self._auth_repo.update_spotify_auth(spotify_auth)

    def add_or_update_spotify_auth(self, spotify_auth: SpotifyAuth) -> SpotifyAuth:
        """Insert or update Spotify OAuth2 credentials (upsert)."""
        return self._auth_repo.add_or_update_spotify_auth(spotify_auth)

    def get_tiktok_auth(self, client_id: str) -> TikTokAuth | None:
        """Retrieve TikTok OAuth2 credentials."""
        return self._auth_repo.get_tiktok_auth(client_id)

    def update_tiktok_auth(self, tiktok_auth: TikTokAuth) -> TikTokAuth | None:
        """Update TikTok OAuth2 credentials."""
        return self._auth_repo.update_tiktok_auth(tiktok_auth)

    def add_or_update_tiktok_auth(self, tiktok_auth: TikTokAuth) -> TikTokAuth:
        """Insert or update TikTok OAuth2 credentials (upsert)."""
        return self._auth_repo.add_or_update_tiktok_auth(tiktok_auth)

    def get_yt_auth(self, client_id: str) -> YtAuth | None:
        """Retrieve YouTube OAuth2 credentials."""
        return self._auth_repo.get_yt_auth(client_id)

    def update_yt_auth(self, yt_auth: YtAuth) -> YtAuth | None:
        """Update YouTube OAuth2 credentials."""
        return self._auth_repo.update_yt_auth(yt_auth)

    def add_or_update_yt_auth(self, yt_auth: YtAuth) -> YtAuth:
        """Insert or update YouTube OAuth2 credentials (upsert)."""
        return self._auth_repo.add_or_update_yt_auth(yt_auth)

    # ========================================================================
    # Release Tracking - delegated to ReleaseRepository
    # ========================================================================

    def get_release(self, release_id: str) -> Release | None:
        """Retrieve release by release_id."""
        # Note: ReleaseRepository.get_release signature differs; adapting here
        table = self._tiny_db.table("release")
        results = table.search(Query().release_id == release_id)
        if not results:
            return None
        return Release.model_validate(results[0])

    def update_release(self, release: Release) -> Release | None:
        """Update existing release."""
        return self._release_repo.update_release(release)

    def add_or_update_release(self, release: Release) -> Release:
        """Insert or update release (upsert)."""
        return self._release_repo.add_or_update_release(release)

    def is_release_at_date(self, release_platform: str, release_date: date) -> bool:
        """Check if a video was released on a platform on the given date."""
        return self._release_repo.is_release_at_date(release_platform, release_date)

    # ========================================================================
    # Complex Orchestration Queries
    # ========================================================================

    def get_top_25_videos(
        self,
        timeseries_range: TimeseriesRange = TimeseriesRange.WEEKLY,
        day: PastDate | None = None,
    ) -> list[Video]:
        """
        Get top 25 videos ranked by growth for a time range.

        Algorithm:
        1. Fetch previous period's videos (WEEKLY baseline)
        2. Fetch current period's videos (DAILY)
        3. Compare: score by growth, assign UP/DOWN/NEW status
        4. Return ranked list
        """
        if day is None:
            day = date.today()

        # Fetch previous period
        previous_list: list[VideoPoint] = list(
            self.get_defined_range_timeseries_videos(timeseries_range, day)
        )

        # Fetch current period
        current_list: list[VideoPoint] = list(
            self.get_defined_range_timeseries_videos(TimeseriesRange.DAILY, day + timedelta(days=1))
        )

        if not current_list:
            error_msg = "No video timeseries for today; run fetch script first"
            logger.error(error_msg)
            raise IndexError(error_msg)

        # Rank and compare
        ranked = VideoPointTools.generate_top_list_compared(current_list, previous_list)
        return [Video.model_validate(vp.model_dump()) for vp in ranked]

    # ========================================================================
    # Private Helpers
    # ========================================================================

    @staticmethod
    def _map_point_video_point(point: Point) -> VideoPoint:
        """Convert TinyFlux Point to VideoPoint model."""
        return VideoPoint(
            time=point.time,
            video_id=point.tags.get("video_id", ""),
            views=point.fields.get("views", 0),
            likes=point.fields.get("likes", 0),
            views_growth=point.fields.get("views_growth"),
            score=point.fields.get("score"),
            score_status=point.tags.get("score_status"),
        )

    def _map_and_enrich(self, point: Point) -> VideoPoint:
        """Convert Point to VideoPoint and enrich with metadata from video table."""
        video_point = self._map_point_video_point(point)
        video_detail = self.get_video(video_point.video_id)
        if video_detail:
            video_point.title = video_detail.title
            video_point.description = video_detail.description
            video_point.channel = video_detail.channel
            video_point.duration = video_detail.duration
        return video_point

    def close(self) -> None:
        """Close all database connections."""
        self._auth_repo.close()
        self._timeseries_repo.close()
        self._release_repo.close()
        self._tiny_db.close()
        self._db.close()


def video_list_mapper_hashtags(video_list: list[Video] | None = None) -> list[str]:
    """Extract unique hashtags from a list of videos."""
    hashtag_set = set()
    if not video_list:
        return []
    for video in video_list:
        hashtag_set.update(video.hashtags_in_description)
    return sorted(list(hashtag_set))
