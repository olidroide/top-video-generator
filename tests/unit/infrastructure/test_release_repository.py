from __future__ import annotations

from datetime import UTC, date, datetime

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
