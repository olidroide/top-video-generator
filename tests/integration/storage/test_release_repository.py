"""Integration tests for ReleaseRepository."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from src.domain.models import Release
from src.infrastructure.storage.release_repository import ReleaseRepository


@pytest.fixture
def repo(tmp_path: Path) -> ReleaseRepository:
    return ReleaseRepository(db_path=str(tmp_path / "test.db"))


def make_release(
    platform: str = "YOUTUBE",
    client_id: str = "user_123",
    release_id: str = "vid_abc",
    published_at: float | None = None,
) -> Release:
    return Release(
        platform=platform,
        client_id=client_id,
        release_id=release_id,
        published_at=published_at or datetime(2026, 3, 31, 12, 0, 0).timestamp(),
    )


class TestReleaseRepositoryAddAndGet:
    def test_add_and_get_release(self, repo: ReleaseRepository) -> None:
        release = make_release()
        repo.add_or_update_release(release)

        result = repo.get_release("YOUTUBE", "user_123")
        assert result is not None
        assert result.platform == "YOUTUBE"
        assert result.release_id == "vid_abc"

    def test_get_returns_none_for_unknown(self, repo: ReleaseRepository) -> None:
        assert repo.get_release("TIKTOK", "nobody") is None

    def test_update_overwrites_existing(self, repo: ReleaseRepository) -> None:
        repo.add_or_update_release(make_release(release_id="old_id"))
        repo.add_or_update_release(make_release(release_id="new_id"))

        result = repo.get_release("YOUTUBE", "user_123")
        assert result is not None
        assert result.release_id == "new_id"

    def test_different_platforms_stored_independently(self, repo: ReleaseRepository) -> None:
        repo.add_or_update_release(make_release(platform="YOUTUBE", release_id="yt_id"))
        repo.add_or_update_release(make_release(platform="TIKTOK", release_id="tt_id"))

        yt = repo.get_release("YOUTUBE", "user_123")
        tt = repo.get_release("TIKTOK", "user_123")

        assert yt is not None and yt.release_id == "yt_id"
        assert tt is not None and tt.release_id == "tt_id"


class TestIsReleaseAtDate:
    def test_returns_true_when_release_exists_on_date(self, repo: ReleaseRepository) -> None:
        ts = datetime(2026, 3, 31, 10, 0, 0).timestamp()
        repo.add_or_update_release(make_release(published_at=ts))

        assert repo.is_release_at_date(platform="YOUTUBE", release_date=date(2026, 3, 31)) is True

    def test_returns_false_when_no_release_on_date(self, repo: ReleaseRepository) -> None:
        ts = datetime(2026, 3, 30, 10, 0, 0).timestamp()
        repo.add_or_update_release(make_release(published_at=ts))

        assert repo.is_release_at_date(platform="YOUTUBE", release_date=date(2026, 3, 31)) is False

    def test_returns_false_when_no_release_at_all(self, repo: ReleaseRepository) -> None:
        assert repo.is_release_at_date(platform="YOUTUBE", release_date=date(2026, 3, 31)) is False

    def test_different_platform_is_not_counted(self, repo: ReleaseRepository) -> None:
        ts = datetime(2026, 3, 31, 10, 0, 0).timestamp()
        repo.add_or_update_release(make_release(platform="TIKTOK", published_at=ts))

        assert repo.is_release_at_date(platform="YOUTUBE", release_date=date(2026, 3, 31)) is False
