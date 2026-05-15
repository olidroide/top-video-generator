"""Unit tests for domain.services.scoring_service module."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from src.domain.exceptions import ScoringError
from src.domain.models import CanonicalVideo, Channel, Video, VideoPoint, VideoScoreStatus
from src.domain.services.scoring_service import (
    calculate_score_status,
    calculate_views_growth,
    datetime_range_start,
    rank_videos_by_score,
    score_and_rank,
    score_and_rank_video_points,
)


def make_video(
    video_id: str = "abc123",
    views: int = 1000,
    score: float = 0.0,
) -> CanonicalVideo:
    """Fixture helper to create test videos."""
    return CanonicalVideo(
        video_id=video_id,
        title=f"Video {video_id}",
        channel_name="Test Channel",
        views=views,
        score=score,
    )


class TestCalculateViewsGrowth:
    """Tests for calculate_views_growth function."""

    def test_no_previous_returns_current_views(self) -> None:
        """If no previous state, growth = current views."""
        video = make_video(views=1000)
        assert calculate_views_growth(video, None) == 1000

    def test_growth_is_absolute_difference(self) -> None:
        """Growth is abs(current - previous)."""
        current = make_video(views=1500)
        previous = make_video(views=1000)
        assert calculate_views_growth(current, previous) == 500

    def test_decline_returns_absolute_value(self) -> None:
        """Declining views still returns absolute difference."""
        current = make_video(views=800)
        previous = make_video(views=1000)
        assert calculate_views_growth(current, previous) == 200

    def test_zero_growth_when_same_views(self) -> None:
        """If views unchanged, growth is 0."""
        current = make_video(views=1000)
        previous = make_video(views=1000)
        assert calculate_views_growth(current, previous) == 0


class TestCalculateScoreStatus:
    """Tests for calculate_score_status function."""

    def test_new_when_no_previous(self) -> None:
        """No previous score → NEW status."""
        assert calculate_score_status(1.0, None) == VideoScoreStatus.NEW

    def test_up_when_rank_improves(self) -> None:
        """Lower score = better rank. score 1 vs previous 3 → UP."""
        assert calculate_score_status(1.0, 3.0) == VideoScoreStatus.UP

    def test_down_when_rank_drops(self) -> None:
        """Higher score = worse rank. score 5 vs previous 2 → DOWN."""
        assert calculate_score_status(5.0, 2.0) == VideoScoreStatus.DOWN

    def test_equal_when_same_rank(self) -> None:
        """Same score → EQUAL status."""
        assert calculate_score_status(3.0, 3.0) == VideoScoreStatus.EQUAL


class TestScoreAndRank:
    """Tests for score_and_rank function."""

    def test_raises_on_empty_current(self) -> None:
        """Empty current list → ScoringError."""
        with pytest.raises(ScoringError, match="current video list is empty"):
            score_and_rank(current=[], previous=[])

    def test_ranks_by_views_growth_descending(self) -> None:
        """Videos ranked by views_growth DESC (most growth = rank #1)."""
        current = [make_video("v1", views=5000), make_video("v2", views=9000)]
        previous = [make_video("v1", views=4000), make_video("v2", views=1000)]
        result = score_and_rank(current, previous)

        # v2 grew 8000, v1 grew 1000 → v2 should be rank #1
        assert result[0].video_id == "v2"
        assert result[0].score == 1.0
        assert result[1].video_id == "v1"
        assert result[1].score == 2.0

    def test_new_video_gets_new_status(self) -> None:
        """New video (not in previous) → score_previous=None, status=NEW."""
        current = [make_video("new_v", views=500)]
        result = score_and_rank(current, previous=[])

        assert result[0].video_id == "new_v"
        assert result[0].score_previous is None
        assert result[0].score_status == VideoScoreStatus.NEW

    def test_existing_video_gets_status_change(self) -> None:
        """Existing video with rank change → status reflects movement."""
        current = [make_video("v1", views=9000)]
        previous = [make_video("v1", views=1000, score=1.0)]  # was rank #1 before
        result = score_and_rank(current, previous)

        assert result[0].score == 1.0
        assert result[0].score_previous == 1.0  # was also #1 before
        assert result[0].score_status == VideoScoreStatus.EQUAL

    def test_no_mutation_of_input(self) -> None:
        """score_and_rank must NOT mutate input lists."""
        original_views = 5000
        current = [make_video("v1", views=original_views)]
        original_current = current.copy()

        score_and_rank(current, previous=[])

        # Input should be unchanged (CanonicalVideo is frozen)
        assert current[0].views == original_views
        assert current == original_current

    def test_all_videos_assigned_unique_scores(self) -> None:
        """Scores are 1-based positions, all unique."""
        current = [
            make_video("v1", views=500),
            make_video("v2", views=2000),
            make_video("v3", views=1000),
        ]
        result = score_and_rank(current, previous=[])

        scores = [v.score for v in result]
        assert scores == [1.0, 2.0, 3.0]

    def test_preserves_video_metadata(self) -> None:
        """Original video metadata (title, channel, etc) preserved."""
        original = make_video("v1", views=1000)
        result = score_and_rank([original], previous=[])

        assert result[0].title == original.title
        assert result[0].channel_name == original.channel_name
        assert result[0].views == original.views


class TestDatetimeRangeStart:
    """Tests for datetime_range_start function."""

    def test_no_mutable_default(self) -> None:
        """Calling the function twice should not return cached date."""
        ref1 = date(2026, 3, 5)
        ref2 = date(2026, 3, 6)

        result1 = datetime_range_start(7, reference=ref1)
        result2 = datetime_range_start(7, reference=ref2)

        assert result1 != result2

    def test_correct_days_back(self) -> None:
        """Should compute correct date N days in the past."""
        ref = date(2026, 3, 5)
        result = datetime_range_start(7, reference=ref)

        expected = datetime(2026, 2, 26, 0, 0, 0, tzinfo=UTC)
        assert result == expected

    def test_time_is_midnight(self) -> None:
        """Result should always be at 00:00:00."""
        result = datetime_range_start(1, reference=date(2026, 3, 5))
        assert result.hour == 0
        assert result.minute == 0
        assert result.second == 0

    def test_zero_days_back_returns_today(self) -> None:
        """days_back=0 should return midnight of reference date."""
        ref = date(2026, 3, 5)
        result = datetime_range_start(0, reference=ref)
        expected = datetime(2026, 3, 5, 0, 0, 0, tzinfo=UTC)
        assert result == expected


class TestScoreAndRankVideoPoints:
    def test_assigns_rank_and_status_for_video_points(self) -> None:
        previous = [
            VideoPoint(
                time=datetime(2026, 3, 30, 0, 0, tzinfo=UTC),
                video_id="v1",
                views=1000,
                likes=10,
                score=1,
            )
        ]
        current = [
            VideoPoint(
                time=datetime(2026, 3, 31, 0, 0, tzinfo=UTC),
                video_id="v1",
                views=1500,
                likes=20,
            ),
            VideoPoint(
                time=datetime(2026, 3, 31, 0, 0, tzinfo=UTC),
                video_id="v2",
                views=3000,
                likes=30,
            ),
        ]

        ranked = score_and_rank_video_points(current, previous)

        assert ranked[0].video_id == "v2"
        assert ranked[0].score == 1
        assert ranked[0].score_status == VideoScoreStatus.NEW
        assert ranked[1].video_id == "v1"
        assert ranked[1].score_previous == 1
        assert ranked[1].score_status == VideoScoreStatus.DOWN

    def test_does_not_mutate_input_video_points(self) -> None:
        previous = [
            VideoPoint(
                time=datetime(2026, 3, 30, 0, 0, tzinfo=UTC),
                video_id="v1",
                views=1000,
                likes=10,
                score=3,
            )
        ]
        current = [
            VideoPoint(
                time=datetime(2026, 3, 31, 0, 0, tzinfo=UTC),
                video_id="v1",
                views=1500,
                likes=20,
            ),
            VideoPoint(
                time=datetime(2026, 3, 31, 0, 0, tzinfo=UTC),
                video_id="v2",
                views=3000,
                likes=30,
            ),
        ]

        original_current = [item.model_copy(deep=True) for item in current]

        ranked = score_and_rank_video_points(current, previous)

        assert current == original_current
        assert ranked is not current
        assert ranked[0] is not current[0]
        assert ranked[1] is not current[1]


class TestRankVideosByScore:
    def _video(self, video_id: str, score: int | None) -> Video:
        return Video(
            video_id=video_id,
            score=score,
            title=f"Title {video_id}",
            channel=Channel(name="Channel", channel_id="cid"),
        )

    def test_orders_by_score_desc_with_none_first(self) -> None:
        videos = [
            self._video("none", None),
            self._video("low", 1),
            self._video("high", 10),
            self._video("mid", 5),
        ]

        ranked = rank_videos_by_score(videos)

        # Mirrors existing weekly publish semantics from entrypoint refactor.
        assert [video.video_id for video in ranked] == ["none", "high", "mid", "low"]

    def test_does_not_mutate_input_list(self) -> None:
        videos = [self._video("a", 2), self._video("b", None)]
        original = list(videos)

        ranked = rank_videos_by_score(videos)

        assert videos == original
        assert ranked is not videos
