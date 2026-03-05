"""Release tracking repository (TinyDB backend)."""

from __future__ import annotations

from datetime import date, datetime

from tinydb import Query, TinyDB

from src.domain.models import Release
from src.shared.logging import get_logger

logger = get_logger(__name__)


class ReleaseRepository:
    """
    Tracks published releases across platforms (YouTube, TikTok, Instagram, Spotify).

    Storage: TinyDB (JSON)
    Table: "release"
    Responsibility: Record when a video was published on which platform.
    """

    _TABLE = "release"

    def __init__(self, db_path: str) -> None:
        """Initialize repository with TinyDB backend."""
        self._db = TinyDB(db_path)

    def get_release(self, platform: str, client_id: str) -> Release | None:
        """
        Retrieve the most recent release for a platform+client_id combination.

        Args:
            platform: Platform name (YOUTUBE, TIKTOK, INSTAGRAM, SPOTIFY).
            client_id: Client ID for the platform.

        Returns:
            Release if found, None otherwise.
        """
        table = self._db.table(self._TABLE)
        query = (Query().platform == platform) & (Query().client_id == client_id)
        results = table.search(query)
        if not results:
            return None
        # Return the most recent (last inserted)
        return Release.model_validate(results[-1])

    def update_release(self, release: Release) -> Release | None:
        """
        Update an existing release record.

        Args:
            release: Release object with platform, client_id, release_id, published_at.

        Returns:
            Updated Release if found, None otherwise.
        """
        table = self._db.table(self._TABLE)
        query = (Query().platform == release.platform) & (Query().client_id == release.client_id)
        table.update(release.model_dump(), query)
        return release

    def add_or_update_release(self, release: Release) -> Release:
        """
        Insert or update a release record (upsert).

        Args:
            release: Release to persist.

        Returns:
            Persisted Release.
        """
        if self.get_release(release.platform, release.client_id):
            return self.update_release(release)
        table = self._db.table(self._TABLE)
        table.insert(release.model_dump())
        return release

    def is_release_at_date(self, platform: str, release_date: date) -> bool:
        """
        Check if a video was released on a specific platform on the given date.

        Args:
            platform: Platform name (YOUTUBE, TIKTOK, INSTAGRAM, SPOTIFY).
            release_date: Date to check.

        Returns:
            True if a release exists for this platform on this date, False otherwise.
        """
        table = self._db.table(self._TABLE)
        results = table.search(Query().platform == platform)

        if not results:
            return False

        # Check if any release timestamp falls on the given date
        for result in results:
            release = Release.model_validate(result)
            if release.published_at is None:
                continue
            published_date = datetime.fromtimestamp(release.published_at).date()
            if published_date == release_date:
                return True

        return False

    def clear_releases_for_platform(self, platform: str) -> int:
        """
        Delete all releases for a platform (use with caution).

        Args:
            platform: Platform name.

        Returns:
            Number of records deleted.
        """
        table = self._db.table(self._TABLE)
        return len(table.remove(Query().platform == platform))

    def close(self) -> None:
        """Close database connection."""
        self._db.close()
