"""Domain service for video scoring and ranking logic."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from src.domain.exceptions import ScoringError
from src.domain.models import CanonicalVideo, VideoPoint, VideoScoreStatus


def calculate_views_growth(current: CanonicalVideo, previous: CanonicalVideo | None) -> int:
    """
    Calculate absolute difference in views between current and previous state.

    If no previous state, return current views (initial growth).
    """
    if previous is None:
        return current.views
    return abs(current.views - previous.views)


def calculate_score_status(
    current_score: float,
    previous_score: float | None,
) -> VideoScoreStatus:
    """
    Determine if video rank improved, declined, stayed same, or is new.

    Note: lower score = better rank (score=1.0 is #1).
    """
    if previous_score is None:
        return VideoScoreStatus.NEW
    if current_score == previous_score:
        return VideoScoreStatus.EQUAL
    if current_score > previous_score:  # ← higher score = worse rank
        return VideoScoreStatus.DOWN
    return VideoScoreStatus.UP


def score_and_rank(
    current: list[CanonicalVideo],
    previous: list[CanonicalVideo],
) -> list[CanonicalVideo]:
    """
    Pure function: rank videos by views_growth, assign scores, compute status changes.

    Args:
        current: List of videos in current state (may have new or missing videos).
        previous: List of videos from previous fetch (used for growth/status calculation).

    Returns:
        List of enriched CanonicalVideo with:
        - views_growth: abs(current.views - previous.views)
        - score: float position (1.0 = rank #1)
        - score_previous: float of previous position, or None if video is new

    Raises:
        ScoringError: If current list is empty.

    Side effects: NONE. This function is fully pure and testable.
    """
    if not current:
        raise ScoringError("current video list is empty")

    # Build lookup of previous state by video_id
    previous_by_id: dict[str, CanonicalVideo] = {v.video_id: v for v in previous}

    # Enrich with views_growth
    enriched = [
        v.model_copy(update={"views_growth": calculate_views_growth(v, previous_by_id.get(v.video_id))})
        for v in current
    ]

    # Rank by views_growth DESC (most growth = rank #1)
    ranked = sorted(enriched, key=lambda v: v.views_growth, reverse=True)

    # Assign scores (1-based position) and compute status
    result: list[CanonicalVideo] = []
    for rank, video in enumerate(ranked, start=1):
        prev = previous_by_id.get(video.video_id)
        prev_score: float | None = float(prev.score) if prev and prev.score is not None else None

        result.append(
            video.model_copy(
                update={
                    "score": float(rank),
                    "score_previous": prev_score,
                    "score_status": calculate_score_status(float(rank), prev_score),
                }
            )
        )
    return result


def score_and_rank_video_points(
    current: list[VideoPoint],
    previous: list[VideoPoint],
) -> list[VideoPoint]:
    """Rank VideoPoint items by growth and assign score/status metadata."""
    if not current:
        raise ScoringError("current video list is empty")

    previous_by_id: dict[str, VideoPoint] = {video.video_id: video for video in previous}

    for video_point in current:
        prev = previous_by_id.get(video_point.video_id)
        if prev:
            video_point.views_growth = abs(video_point.views - prev.views)
        else:
            video_point.views_growth = video_point.views_growth or video_point.views

    current.sort(key=lambda item: item.views_growth or 0, reverse=True)

    for rank, video_point in enumerate(current, start=1):
        prev = previous_by_id.get(video_point.video_id)
        prev_score = prev.score if prev and prev.score is not None else None
        video_point.score = rank
        video_point.score_previous = prev_score
        video_point.score_status = calculate_score_status(
            float(rank),
            float(prev_score) if prev_score is not None else None,
        )

    return current


def datetime_range_start(
    days_back: int,
    reference: date | None = None,
) -> datetime:
    """
    Compute start of datetime range N days in the past.

    Args:
        days_back: Number of days to go back (e.g., 7 for "last week").
        reference: Base date (defaults to today). Must be passed explicitly to avoid
                   mutable-default-argument bugs.

    Returns:
        datetime at 00:00:00 on the computed date.

    Example:
        >>> datetime_range_start(7, reference=date(2026, 3, 5))
        datetime(2026, 2, 26, 0, 0, 0)
    """
    ref = reference or datetime.now(UTC).date()
    target_date = ref - timedelta(days=days_back)
    return datetime.combine(target_date, datetime.min.time(), tzinfo=UTC)
