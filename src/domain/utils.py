"""Utilities for video data transformations and mappings."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.models import Video


def extract_video_hashtags(video_list: list[Video] | None = None) -> list[str]:
    """
    Extract unique hashtags from a list of videos.

    Args:
        video_list: List of Video objects to extract hashtags from.

    Returns:
        Sorted list of unique hashtags found in video descriptions.
    """
    if not video_list:
        return []

    hashtag_set = set()
    for video in video_list:
        hashtag_set.update(video.hashtags_in_description)

    return sorted(list(hashtag_set))
