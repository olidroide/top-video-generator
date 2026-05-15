from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.domain.models import Video
from src.entrypoints.workers.post_processor import _process_video


def test_process_video_returns_error_when_video_id_is_empty() -> None:
    compositor = MagicMock()

    result = _process_video(video=Video(video_id="   "), compositor=compositor, screen_orientation="vertical")

    assert result["status"] == "error"
    assert result["error"] == "video_id is empty"
    compositor.post_process_vertical_video.assert_not_called()
    compositor.post_process_video.assert_not_called()


def test_process_video_uses_vertical_handler() -> None:
    compositor = MagicMock()
    compositor.post_process_vertical_video.return_value = object()

    with patch("src.entrypoints.workers.post_processor.asyncio.run") as asyncio_run:
        result = _process_video(video=Video(video_id="abc123"), compositor=compositor, screen_orientation="vertical")

    assert result == {"video_id": "abc123", "status": "ok"}
    asyncio_run.assert_called_once_with(compositor.post_process_vertical_video.return_value)


def test_process_video_returns_error_when_handler_raises() -> None:
    compositor = MagicMock()
    compositor.post_process_video.return_value = object()

    with patch("src.entrypoints.workers.post_processor.asyncio.run", side_effect=RuntimeError("boom")):
        result = _process_video(video=Video(video_id="abc123"), compositor=compositor, screen_orientation="horizontal")

    assert result["status"] == "error"
    assert result["video_id"] == "abc123"
    assert result["error"] == "boom"
