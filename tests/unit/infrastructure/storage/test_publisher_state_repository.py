"""Tests for PublisherStateRepository."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.infrastructure.storage.publisher_state_repository import PublisherStateRepository


@pytest.fixture
def repo(tmp_path: Path) -> PublisherStateRepository:
    db_file = tmp_path / "db_publishers.json"
    return PublisherStateRepository(str(db_file))


class TestPublisherStateRepository:
    def test_is_enabled_default_true(self, repo: PublisherStateRepository) -> None:
        assert repo.is_enabled("youtube") is True

    def test_set_enabled_false(self, repo: PublisherStateRepository) -> None:
        repo.set_enabled("youtube", False)
        assert repo.is_enabled("youtube") is False

    def test_set_enabled_true_after_false(self, repo: PublisherStateRepository) -> None:
        repo.set_enabled("youtube", False)
        repo.set_enabled("youtube", True)
        assert repo.is_enabled("youtube") is True

    def test_get_all_empty(self, repo: PublisherStateRepository) -> None:
        assert repo.get_all() == {}

    def test_get_all_with_multiple_platforms(self, repo: PublisherStateRepository) -> None:
        repo.set_enabled("youtube", True)
        repo.set_enabled("tiktok", False)
        repo.set_enabled("instagram", True)

        result = repo.get_all()
        assert result == {"youtube": True, "tiktok": False, "instagram": True}

    def test_is_enabled_independent_per_platform(self, repo: PublisherStateRepository) -> None:
        repo.set_enabled("tiktok", False)
        assert repo.is_enabled("youtube") is True
        assert repo.is_enabled("tiktok") is False

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        nested = tmp_path / "sub" / "dir" / "db_publishers.json"
        PublisherStateRepository(str(nested))
        assert nested.exists()
