"""Domain service for generating video metadata (titles, descriptions)."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from src.domain.models import Video


def generate_youtube_title(
    video_list: Sequence[Video],
    title_template: str,
    hashtags: list[str] | None = None,
) -> str:
    """
    Generate YouTube video title from template.

    Args:
        video_list: Videos to generate title for.
        title_template: Template with @@TOP_DATE@@ and @@HASHTAGS@@ placeholders.
        hashtags: Optional list of hashtags to include.

    Returns:
        Formatted title string.
    """
    text_date = datetime.datetime.now(datetime.UTC).strftime("%d/%m/%Y")
    hashtags_str = " ".join(hashtags) if hashtags else ""
    return title_template.replace("@@TOP_DATE@@", f"[{text_date}] #top{len(video_list)}").replace(
        "@@HASHTAGS@@", f"\n{hashtags_str}"
    )


def generate_youtube_description(
    video_list: Sequence[Video],
    description_template: str,
) -> str:
    """
    Generate YouTube video description from template.

    Args:
        video_list: Videos to generate description for.
        description_template: Template with @@TOP_DATE@@, @@VIDEO_LIST@@, and @@DISCLAIMER@@ placeholders.

    Returns:
        Formatted description string.
    """
    text_date = datetime.datetime.now(datetime.UTC).strftime("%d/%m/%Y")
    channels_names = sorted({video.channel.name for video in video_list if video.channel and video.channel.name})
    original_publishers = ",".join(channels_names)

    fair_use_text = (
        "As per the 3rd section of fair use guidelines borrowing small bits of material from "
        "an original work is more likely to be considered fair use. Copyright disclaimer under "
        "section 107 of the copyright act 1976, allowance is made for fair use"
    )
    legal_notice = (
        "This publication and the information included in it are not intended to serve "
        "a substitute for consultation with an attonery."
    )
    copyright_notice = (
        "Please note no copyright infringement is intended, and I do not own nor claim "
        "to own any of the original publishers recordings used in this video. "
        f"Original publishers : {original_publishers}."
    )
    disclaimer = f"------\nDisclaimer\n  - {legal_notice}\n\n  - {copyright_notice}\n\n  - {fair_use_text}\n------"

    video_list_names = ""
    for video in video_list:
        video_list_names += f"{video.score}.- {video.title_cleaned} {video.yt_video_url} \n"
        if video.channel and video.channel.name:
            video_list_names += f"© {video.channel.name}\n\n"

    return (
        description_template.replace("@@TOP_DATE@@", f"{text_date} #top{len(video_list)}")
        .replace("@@VIDEO_LIST@@", f"{video_list_names}")
        .replace("@@DISCLAIMER@@", disclaimer)
    )
