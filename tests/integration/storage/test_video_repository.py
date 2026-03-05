"""Integration tests for VideoRepository."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.domain.models import CanonicalVideo
from src.infrastructure.storage.video_repository import VideoRepository


@pytest.fixture
def repo(tmp_path: Path) -> VideoRepository:
    """Fixture: fresh VideoRepository with temporary database."""
    return VideoRepository(db_path=tmp_path / "test.db")


def make_video(
    video_id: str = "abc123",
    title: str = "Test Song",
) -> CanonicalVideo:
    """Helper to create test videos."""
    return CanonicalVideo(
        video_id=video_id,
        title=title,
        channel_name="Test Artist",
        views=1000,
    )


class TestVideoRepositoryUpsertAndGet:
    """Tests for insert/update and retrieval."""

    def test_upsert_and_get_roundtrip(self, repo: VideoRepository) -> None:
        """Insert a video and retrieve it."""
        video = make_video()
        repo.upsert(video)

        result = repo.get(video.video_id)
        assert result is not None
        assert result.video_id == video.video_id
        assert result.title == video.title
        assert result.channel_name == video.channel_name

    def test_upsert_updates_existing(self, repo: VideoRepository) -> None:
        """Updating an existing video should overwrite."""
        repo.upsert(make_video("v1", title="Original Title"))

        updated_video = make_video("v1", title="Updated Title").model_copy(update={"views": 9999})
        repo.upsert(updated_video)

        result = repo.get("v1")
        assert result is not None
        assert result.title == "Updated Title"
        assert result.views == 9999

    def test_get_returns_none_for_unknown(self, repo: VideoRepository) -> None:
        """Retrieving unknown video should return None."""
        assert repo.get("nonexistent") is None

    def test_upsert_multiple_videos(self, repo: VideoRepository) -> None:
        """Can insert multiple videos."""
        videos = [make_video(f"v{i}", title=f"Song {i}") for i in range(3)]
        for video in videos:
            repo.upsert(video)

        for video in videos:
            result = repo.get(video.video_id)
            assert result is not None
            assert result.video_id == video.video_id


class TestVideoRepositorySearch:
    """Tests for search functionality."""

    def test_search_by_video_id_pattern(self, repo: VideoRepository) -> None:
        """Search should find videos matching regex pattern."""
        repo.upsert(make_video("song_abc123"))
        repo.upsert(make_video("song_xyz789"))

        results = repo.search("^song_abc.*")
        assert len(results) == 1
        assert results[0].video_id == "song_abc123"

    def test_search_case_insensitive(self, repo: VideoRepository) -> None:
        """Search should be case-insensitive."""
        repo.upsert(make_video("MyVideo123"))

        results = repo.search("myvideo.*")
        assert len(results) == 1
        assert results[0].video_id == "MyVideo123"

    def test_search_empty_result(self, repo: VideoRepository) -> None:
        """Search with no matches returns empty list."""
        results = repo.search("^nomatch.*")
        assert results == []


class TestVideoRepositoryDelete:
    """Tests for delete functionality."""

    def test_delete_existing_video(self, repo: VideoRepository) -> None:
        """Delete should remove video from storage."""
        repo.upsert(make_video("v1"))
        assert repo.get("v1") is not None

        repo.delete("v1")
        assert repo.get("v1") is None

    def test_delete_nonexistent_returns_zero(self, repo: VideoRepository) -> None:
        """Deleting unknown video returns 0."""
        result = repo.delete("nonexistent")
        assert result == 0

    def test_delete_returns_count(self, repo: VideoRepository) -> None:
        """Delete should return number of deleted records."""
        repo.upsert(make_video("v1"))
        result = repo.delete("v1")
        assert result == 1


class TestVideoRepositoryAll:
    """Tests for retrieving all videos."""

    def test_all_returns_all_videos(self, repo: VideoRepository) -> None:
        """all() should return all inserted videos."""
        videos = [make_video(f"v{i}") for i in range(3)]
        for video in videos:
            repo.upsert(video)

        results = repo.all()
        assert len(results) == 3

    def test_all_returns_empty_when_no_videos(self, repo: VideoRepository) -> None:
        """all() on empty repository returns empty list."""
        results = repo.all()
        assert results == []


class TestVideoRepositoryClear:
    """Tests for clearing all data."""

    def test_clear_removes_all_videos(self, repo: VideoRepository) -> None:
        """clear() should delete all videos."""
        for i in range(3):
            repo.upsert(make_video(f"v{i}"))

        repo.clear()
        assert repo.all() == []


class TestVideoRepositoryDataIntegrity:
    """Tests for data integrity and preservation."""

    def test_preserves_all_video_fields(self, repo: VideoRepository) -> None:
        """All CanonicalVideo fields should survive roundtrip."""
        original = CanonicalVideo(
            video_id="test123",
            title="Test Title",
            channel_name="Test Channel",
            views=5000,
            likes=250,
            description="Test Description",
            duration_seconds=180.5,
        )
        repo.upsert(original)

        result = repo.get("test123")
        assert result is not None
        assert result.video_id == original.video_id
        assert result.title == original.title
        assert result.channel_name == original.channel_name
        assert result.views == original.views
        assert result.likes == original.likes
        assert result.description == original.description
        assert result.duration_seconds == original.duration_seconds
