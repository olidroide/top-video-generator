"""Release tracking repository (TinyDB backend)."""

from __future__ import annotations

from datetime import UTC, date, datetime

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

    def get_release(self, platform: str, client_id: str, release_kind: str | None = None) -> Release | None:
        """
        Retrieve the most recent release for a platform+client_id combination.

        Args:
            platform: Platform name (YOUTUBE, TIKTOK, INSTAGRAM, SPOTIFY).
            client_id: Client ID for the platform.
            release_kind: Optional release category for scoped idempotency.

        Returns:
            Release if found, None otherwise.
        """
        table = self._db.table(self._TABLE)
        query = (Query().platform == platform) & (Query().client_id == client_id)
        results = table.search(query)
        if not results:
            return None
        if release_kind is not None:
            results = [result for result in results if result.get("release_kind") == release_kind]
            if not results:
                return None
        # Return the most recent (last inserted)
        return Release.model_validate(results[-1])

    def update_release(self, release: Release) -> Release:
        """
        Update an existing release record.

        Args:
            release: Release object with platform, client_id, release_id, published_at.

        Returns:
            Updated Release if found, None otherwise.
        """
        table = self._db.table(self._TABLE)
        platform = release.platform or ""
        client_id = release.client_id or ""
        matching_docs = self._get_matching_release_documents(
            platform=platform,
            client_id=client_id,
            release_kind=release.release_kind,
        )
        if matching_docs:
            table.update(release.model_dump(), doc_ids=[matching_docs[-1].doc_id])
        return release

    def add_or_update_release(self, release: Release) -> Release:
        """
        Insert or update a release record (upsert).

        Args:
            release: Release to persist.

        Returns:
            Persisted Release.
        """
        platform = release.platform or ""
        client_id = release.client_id or ""
        if self.get_release(platform, client_id, release.release_kind):
            return self.update_release(release)
        table = self._db.table(self._TABLE)
        table.insert(release.model_dump())
        return release

    def is_release_at_date(self, platform: str, release_date: date, release_kind: str | None = None) -> bool:
        """
        Check if a video was released on a specific platform on the given date.

        Args:
            platform: Platform name (YOUTUBE, TIKTOK, INSTAGRAM, SPOTIFY).
            release_date: Date to check.
            release_kind: Optional release category for scoped idempotency.

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
            if release_kind is not None and release.release_kind not in {None, release_kind}:
                continue
            if release.published_at is None:
                continue
            published_date = datetime.fromtimestamp(release.published_at, tz=UTC).date()
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

    def _get_matching_release_documents(self, platform: str, client_id: str, release_kind: str | None) -> list:
        """Return stored release documents matching platform, client and exact kind."""
        table = self._db.table(self._TABLE)
        query = (Query().platform == platform) & (Query().client_id == client_id)
        results = table.search(query)
        if release_kind is None:
            return [result for result in results if result.get("release_kind") is None]
        return [result for result in results if result.get("release_kind") == release_kind]
