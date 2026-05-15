"""Integration tests for TimeSeriesRepository."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from tinyflux import Point

from src.domain.models import Channel, VideoPoint, VideoScoreStatus
from src.infrastructure.storage.timeseries_repository import TimeSeriesRepository


@pytest.fixture
def repo(tmp_path: Path) -> TimeSeriesRepository:
    return TimeSeriesRepository(db_path=str(tmp_path / "test_timeseries.csv"))


def make_point(
    video_id: str = "vid_abc",
    views: int = 1000,
    likes: int = 50,
    views_growth: int | None = 200,
    score: int | None = 5,
    score_status: VideoScoreStatus = VideoScoreStatus.NEW,
    dt: datetime | None = None,
) -> VideoPoint:
    return VideoPoint(
        time=dt or datetime(2026, 3, 31, 12, 0, 0, tzinfo=UTC),
        video_id=video_id,
        views=views,
        likes=likes,
        views_growth=views_growth,
        score=score,
        score_status=score_status,
    )


class TestAddVideoPoint:
    def test_insert_and_retrieve_by_video_id(self, repo: TimeSeriesRepository) -> None:
        point = make_point(video_id="v1", views=2000)
        repo.add_video_point(point)

        results = repo.get_all_points_by_video("v1")
        assert len(results) == 1
        assert results[0].fields["views"] == 2000

    def test_multiple_points_for_same_video(self, repo: TimeSeriesRepository) -> None:
        t1 = datetime(2026, 3, 30, 12, 0, 0, tzinfo=UTC)
        t2 = datetime(2026, 3, 31, 12, 0, 0, tzinfo=UTC)
        repo.add_video_point(make_point(video_id="v1", views=1000, dt=t1))
        repo.add_video_point(make_point(video_id="v1", views=1500, dt=t2))

        results = repo.get_all_points_by_video("v1")
        assert len(results) == 2

    def test_different_videos_separated(self, repo: TimeSeriesRepository) -> None:
        repo.add_video_point(make_point(video_id="v1"))
        repo.add_video_point(make_point(video_id="v2"))

        assert len(repo.get_all_points_by_video("v1")) == 1
        assert len(repo.get_all_points_by_video("v2")) == 1
        assert len(repo.get_all_points_by_video("v999")) == 0


class TestGetVideoPointsByDateRange:
    def test_returns_points_within_range(self, repo: TimeSeriesRepository) -> None:
        t_inside = datetime(2026, 3, 31, 12, 0, 0, tzinfo=UTC)
        t_outside = datetime(2026, 3, 28, 12, 0, 0, tzinfo=UTC)
        repo.add_video_point(make_point(video_id="v1", dt=t_inside))
        repo.add_video_point(make_point(video_id="v2", dt=t_outside))

        start = datetime(2026, 3, 30, 0, 0, 0, tzinfo=UTC)
        end = datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC)
        results = repo.get_video_points_by_date_range(start, end)

        ids = {r.video_id for r in results}
        assert "v1" in ids
        assert "v2" not in ids

    def test_returns_empty_when_no_data_in_range(self, repo: TimeSeriesRepository) -> None:
        repo.add_video_point(make_point(dt=datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)))

        start = datetime(2026, 3, 29, 0, 0, 0, tzinfo=UTC)
        end = datetime(2026, 3, 30, 0, 0, 0, tzinfo=UTC)
        results = repo.get_video_points_by_date_range(start, end)

        assert results == []

    def test_returns_video_points_with_correct_fields(self, repo: TimeSeriesRepository) -> None:
        dt = datetime(2026, 3, 31, 8, 0, 0, tzinfo=UTC)
        repo.add_video_point(make_point(video_id="vX", views=9999, likes=111, views_growth=500, score=3, dt=dt))

        start = datetime(2026, 3, 30, 0, 0, 0, tzinfo=UTC)
        end = datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC)
        results = repo.get_video_points_by_date_range(start, end)

        assert len(results) == 1
        vp = results[0]
        assert vp.video_id == "vX"
        assert vp.views == 9999
        assert vp.likes == 111
        assert vp.score == 3

    def test_does_not_persist_optional_video_metadata_fields(self, repo: TimeSeriesRepository) -> None:
        dt = datetime(2026, 3, 31, 8, 0, 0, tzinfo=UTC)
        point = make_point(video_id="v-meta", views=9999, likes=111, views_growth=500, score=3, dt=dt)
        point.title = "Hydrated title"
        point.description = "Hydrated description"
        point.channel = Channel(name="Hydrated channel")
        point.duration = 182

        repo.add_video_point(point)

        start = datetime(2026, 3, 30, 0, 0, 0, tzinfo=UTC)
        end = datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC)
        results = repo.get_video_points_by_date_range(start, end)

        assert len(results) == 1
        vp = results[0]
        assert vp.video_id == "v-meta"
        assert vp.title is None
        assert vp.description is None
        assert vp.channel is None
        assert vp.duration is None

    def test_maps_nullable_numeric_fields_to_none(self) -> None:
        dt = datetime(2026, 3, 31, 10, 0, 0, tzinfo=UTC)
        point = Point(
            measurement="Video visualizations",
            time=dt,
            tags={"video_id": "v-null", "score_status": "NEW"},
            fields={"views": 1500, "likes": 75, "views_growth": None, "score": None},
        )
        result = TimeSeriesRepository._map_point(point)

        assert result.views_growth is None
        assert result.score is None

    def test_map_point_raises_when_time_is_missing(self) -> None:
        point = SimpleNamespace(
            time=None,
            tags={"video_id": "v-missing-time"},
            fields={"views": 1, "likes": 1},
        )

        with pytest.raises(ValueError, match="missing time"):
            TimeSeriesRepository._map_point(point)


class TestGetLastTimestamp:
    def test_returns_none_when_empty(self, repo: TimeSeriesRepository) -> None:
        assert repo.get_last_timestamp() is None

    def test_returns_latest_timestamp(self, repo: TimeSeriesRepository) -> None:
        t1 = datetime(2026, 3, 30, 0, 0, 0, tzinfo=UTC)
        t2 = datetime(2026, 3, 31, 0, 0, 0, tzinfo=UTC)
        repo.add_video_point(make_point(dt=t1))
        repo.add_video_point(make_point(dt=t2))

        last = repo.get_last_timestamp()
        assert last is not None
        assert last.date() == t2.date()
