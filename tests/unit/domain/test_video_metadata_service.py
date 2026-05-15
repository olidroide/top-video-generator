"""Unit tests for video metadata service."""

from src.domain.models import Channel, Video
from src.domain.services.video_metadata_service import generate_youtube_description, generate_youtube_title


def test_generate_youtube_title_with_hashtags() -> None:
    """Test title generation includes hashtags and date."""
    video1 = Video(
        video_id="vid1",
        title="Test Video 1",
        channel=Channel(name="Test Channel"),
        views=1000,
        score=1,
    )
    video2 = Video(
        video_id="vid2",
        title="Test Video 2",
        channel=Channel(name="Test Channel 2"),
        views=800,
        score=2,
    )

    template = "Top @@TOP_DATE@@ @@HASHTAGS@@"
    hashtags = ["#music", "#trending"]

    result = generate_youtube_title(
        video_list=[video1, video2],
        title_template=template,
        hashtags=hashtags,
    )

    assert "#top2" in result
    assert "#music" in result
    assert "#trending" in result
    assert "Top " in result


def test_generate_youtube_title_without_hashtags() -> None:
    """Test title generation without hashtags."""
    video = Video(
        video_id="vid1",
        title="Test Video",
        channel=Channel(name="Test Channel"),
        views=1000,
        score=1,
    )

    template = "Top @@TOP_DATE@@ @@HASHTAGS@@"

    result = generate_youtube_title(
        video_list=[video],
        title_template=template,
        hashtags=None,
    )

    assert "#top1" in result
    assert "Top " in result


def test_generate_youtube_description() -> None:
    """Test description generation includes video list and disclaimer."""
    video = Video(
        video_id="vid1",
        title="Test Video",
        channel=Channel(name="Test Channel"),
        views=1000,
        score=1,
    )

    template = "Date: @@TOP_DATE@@ Videos: @@VIDEO_LIST@@ Disclaimer: @@DISCLAIMER@@"

    result = generate_youtube_description(
        video_list=[video],
        description_template=template,
    )

    assert "#top1" in result
    assert "1" in result  # score
    assert "Test Video" in result
    assert "Disclaimer:" in result
    assert "fair use" in result
    assert "Test Channel" in result


def test_generate_youtube_description_multiple_videos() -> None:
    """Test description with multiple videos from different channels."""
    videos = [
        Video(
            video_id=f"vid{i}",
            title=f"Video {i}",
            channel=Channel(name=f"Channel {i}"),
            views=1000 - i * 100,
            score=i,
        )
        for i in range(1, 4)
    ]

    template = "Videos: @@VIDEO_LIST@@"

    result = generate_youtube_description(
        video_list=videos,
        description_template=template,
    )

    # Check all videos are listed
    assert "Video 1" in result
    assert "Video 2" in result
    assert "Video 3" in result
    # Check all channels are listed (sorted)
    assert "Channel 1" in result
    assert "Channel 2" in result
    assert "Channel 3" in result
    # Check scores are present
    assert "1" in result
    assert "2" in result
    assert "3" in result
