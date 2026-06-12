from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, date, datetime

import pytest

from src.domain.models import Platform, Release, ReleaseKind
from src.infrastructure.storage.release_repository import ReleaseRepository


def test_add_or_update_release_keeps_daily_and_weekly_records_separate(tmp_path) -> None:
    repo = ReleaseRepository(str(tmp_path / "db.json"))
    published_at = datetime(2026, 3, 31, tzinfo=UTC).timestamp()

    try:
        repo.add_or_update_release(
            Release(
                platform=Platform.YOUTUBE.value,
                client_id="creator",
                release_kind=ReleaseKind.DAILY_VERTICAL.value,
                release_id="daily-id",
                published_at=published_at,
            )
        )
        repo.add_or_update_release(
            Release(
                platform=Platform.YOUTUBE.value,
                client_id="creator",
                release_kind=ReleaseKind.WEEKLY_HORIZONTAL.value,
                release_id="weekly-id",
                published_at=published_at,
            )
        )

        daily_release = repo.get_release(
            platform=Platform.YOUTUBE.value,
            client_id="creator",
            release_kind=ReleaseKind.DAILY_VERTICAL.value,
        )
        weekly_release = repo.get_release(
            platform=Platform.YOUTUBE.value,
            client_id="creator",
            release_kind=ReleaseKind.WEEKLY_HORIZONTAL.value,
        )

        assert daily_release is not None
        assert daily_release.release_id == "daily-id"
        assert weekly_release is not None
        assert weekly_release.release_id == "weekly-id"
    finally:
        repo.close()


def test_is_release_at_date_accepts_legacy_unscoped_release_for_transition(tmp_path) -> None:
    repo = ReleaseRepository(str(tmp_path / "db.json"))
    release_date = date(2026, 3, 31)

    try:
        repo.add_or_update_release(
            Release(
                platform=Platform.YOUTUBE.value,
                client_id="creator",
                release_id="legacy-id",
                published_at=datetime(2026, 3, 31, 9, 0, tzinfo=UTC).timestamp(),
            )
        )

        assert repo.is_release_at_date(
            platform=Platform.YOUTUBE.value,
            release_date=release_date,
            release_kind=ReleaseKind.WEEKLY_HORIZONTAL.value,
        )
    finally:
        repo.close()


def test_get_latest_release_returns_latest_by_published_at(tmp_path) -> None:
    repo = ReleaseRepository(str(tmp_path / "db.json"))
    try:
        repo.add_or_update_release(
            Release(
                platform=Platform.YOUTUBE.value,
                client_id="creator",
                release_kind=ReleaseKind.DAILY_VERTICAL.value,
                release_id="old-id",
                published_at=datetime(2026, 3, 30, 9, 0, tzinfo=UTC).timestamp(),
            )
        )
        repo.add_or_update_release(
            Release(
                platform=Platform.YOUTUBE.value,
                client_id="creator-2",
                release_kind=ReleaseKind.DAILY_VERTICAL.value,
                release_id="new-id",
                published_at=datetime(2026, 3, 31, 9, 0, tzinfo=UTC).timestamp(),
            )
        )

        latest = repo.get_latest_release(
            platform=Platform.YOUTUBE.value,
            release_kind=ReleaseKind.DAILY_VERTICAL.value,
        )

        assert latest is not None
        assert latest.release_id == "new-id"
    finally:
        repo.close()


# ---------------------------------------------------------------------------
# add_or_update_release
# ---------------------------------------------------------------------------


class TestAddOrUpdateRelease:
    """Exhaustive contract coverage for add_or_update_release.

    The method is append-only: every call inserts a new row.
    Real idempotency (preventing duplicate publishes on the same day) is the
    responsibility of `is_release_at_date` upstream.
    """

    @pytest.fixture()
    def repo(self, tmp_path) -> Generator[ReleaseRepository]:
        r = ReleaseRepository(str(tmp_path / "db.json"))
        yield r
        r.close()

    def _make_release(
        self,
        *,
        platform: str = Platform.YOUTUBE.value,
        client_id: str = "creator",
        release_kind: str | None = ReleaseKind.DAILY_VERTICAL.value,
        release_id: str = "vid-001",
        published_at: float | None = None,
    ) -> Release:
        if published_at is None:
            published_at = datetime(2026, 6, 10, 14, 0, 0, tzinfo=UTC).timestamp()
        return Release(
            platform=platform,
            client_id=client_id,
            release_kind=release_kind,
            release_id=release_id,
            published_at=published_at,
        )

    # TC-01 — method returns exactly the Release it received
    def test_returns_same_release_object(self, repo: ReleaseRepository) -> None:
        release = self._make_release(release_id="abc")
        result = repo.add_or_update_release(release)
        assert result == release
        assert result.release_id == "abc"
        assert result.platform == Platform.YOUTUBE.value

    # TC-02 — same platform+kind → N independent rows (real append, not upsert)
    def test_creates_multiple_rows_for_same_platform_and_kind(self, repo: ReleaseRepository) -> None:
        ids = ["vid-day1", "vid-day2", "vid-day3"]
        base_ts = datetime(2026, 6, 8, 14, 0, 0, tzinfo=UTC).timestamp()
        for i, rid in enumerate(ids):
            repo.add_or_update_release(
                self._make_release(
                    release_id=rid,
                    published_at=base_ts + i * 86400,
                )
            )

        rows = repo._db.table("release").all()
        assert len(rows) == 3
        stored_ids = {r["release_id"] for r in rows}
        assert stored_ids == set(ids)

    # TC-03 — N calls → exactly N rows (even with identical content)
    def test_row_count_equals_call_count(self, repo: ReleaseRepository) -> None:
        release = self._make_release()
        for _ in range(4):
            repo.add_or_update_release(release)
        assert len(repo._db.table("release").all()) == 4

    # TC-04 — duplicate stored twice but is_release_at_date still returns True
    def test_duplicate_release_id_stored_twice_but_is_release_at_date_still_true(self, repo: ReleaseRepository) -> None:
        release_date = date(2026, 6, 10)
        ts = datetime(2026, 6, 10, 14, 0, 0, tzinfo=UTC).timestamp()
        release = self._make_release(release_id="dup-vid", published_at=ts)

        repo.add_or_update_release(release)
        repo.add_or_update_release(release)  # simulates upstream guard not blocking

        assert len(repo._db.table("release").all()) == 2
        assert (
            repo.is_release_at_date(
                platform=Platform.YOUTUBE.value,
                release_date=release_date,
                release_kind=ReleaseKind.DAILY_VERTICAL.value,
            )
            is True
        )

    # TC-05 — inserting for YOUTUBE does not leak into INSTAGRAM
    def test_cross_platform_isolation(self, repo: ReleaseRepository) -> None:
        repo.add_or_update_release(self._make_release(platform=Platform.YOUTUBE.value))

        assert repo.get_release(platform=Platform.INSTAGRAM.value, client_id="creator") is None
        assert repo.get_latest_release(platform=Platform.INSTAGRAM.value) is None

    # TC-06 — Release with all fields None is stored without error
    def test_all_none_fields_stored_without_error(self, repo: ReleaseRepository) -> None:
        repo.add_or_update_release(Release())
        rows = repo._db.table("release").all()
        assert len(rows) == 1
        row = rows[0]
        assert row["platform"] is None
        assert row["client_id"] is None
        assert row["release_kind"] is None
        assert row["release_id"] is None
        assert row["published_at"] is None

    # TC-07 — full round-trip field fidelity
    def test_round_trip_all_fields(self, repo: ReleaseRepository) -> None:
        ts = datetime(2026, 6, 10, 14, 0, 0, tzinfo=UTC).timestamp()
        original = self._make_release(
            platform=Platform.YOUTUBE.value,
            client_id="creator-full",
            release_kind=ReleaseKind.DAILY_VERTICAL.value,
            release_id="round-trip-id",
            published_at=ts,
        )
        repo.add_or_update_release(original)

        retrieved = repo.get_release(
            platform=Platform.YOUTUBE.value,
            client_id="creator-full",
            release_kind=ReleaseKind.DAILY_VERTICAL.value,
        )
        assert retrieved is not None
        assert retrieved.platform == original.platform
        assert retrieved.client_id == original.client_id
        assert retrieved.release_kind == original.release_kind
        assert retrieved.release_id == original.release_id
        assert retrieved.published_at == pytest.approx(original.published_at)

    # TC-08 — round-trip with release_kind=None: None is preserved, not coerced
    def test_round_trip_none_release_kind_preserved(self, repo: ReleaseRepository) -> None:
        ts = datetime(2026, 6, 10, 14, 0, 0, tzinfo=UTC).timestamp()
        original = Release(
            platform=Platform.YOUTUBE.value,
            client_id="legacy-creator",
            release_kind=None,
            release_id="legacy-vid",
            published_at=ts,
        )
        repo.add_or_update_release(original)

        retrieved = repo.get_release(
            platform=Platform.YOUTUBE.value,
            client_id="legacy-creator",
        )
        assert retrieved is not None
        assert retrieved.release_kind is None
        assert retrieved.client_id == "legacy-creator"

    # TC-09 — same platform, different client_id → no collision
    def test_different_clients_same_platform_stored_independently(self, repo: ReleaseRepository) -> None:
        ts = datetime(2026, 6, 10, 14, 0, 0, tzinfo=UTC).timestamp()
        repo.add_or_update_release(self._make_release(client_id="creator-A", release_id="id-A", published_at=ts))
        repo.add_or_update_release(self._make_release(client_id="creator-B", release_id="id-B", published_at=ts))

        result_a = repo.get_release(platform=Platform.YOUTUBE.value, client_id="creator-A")
        result_b = repo.get_release(platform=Platform.YOUTUBE.value, client_id="creator-B")

        assert result_a is not None
        assert result_a.release_id == "id-A"
        assert result_b is not None
        assert result_b.release_id == "id-B"
        assert len(repo._db.table("release").all()) == 2
