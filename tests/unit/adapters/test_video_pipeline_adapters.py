from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.adapters.horizontal_video_pipeline import HorizontalVideoPipelineAdapter
from src.adapters.vertical_video_pipeline import VerticalVideoPipelineAdapter
from src.config.settings import AppSettings
from src.domain.models import Video


@pytest.mark.asyncio
async def test_vertical_pipeline_filters_invalid_video_ids() -> None:
    settings = AppSettings(yt_search_region_code="ES")
    adapter = VerticalVideoPipelineAdapter(settings)
    invalid_video = Video(video_id="   ")
    valid_video = Video(video_id="abc123")

    downloader_instance = Mock()
    downloader_instance.video_yt_resources_folder = "videos/yt"
    downloader_instance.download_video = AsyncMock()

    worker_factory_instance = Mock()
    compositor_instance = Mock()
    compositor_instance.join_processed_videos = AsyncMock(return_value="/tmp/final_vertical.mp4")

    with (
        patch("src.adapters.vertical_video_pipeline.VideoDownloader", return_value=downloader_instance),
        patch("src.adapters.vertical_video_pipeline.WorkerFactory", return_value=worker_factory_instance),
        patch("src.adapters.vertical_video_pipeline.VideoAssetManager", return_value=SimpleNamespace()),
        patch("src.adapters.vertical_video_pipeline.VideoRenderer", return_value=SimpleNamespace()),
        patch("src.adapters.vertical_video_pipeline.VideoCompositor", return_value=compositor_instance),
    ):
        result = await adapter.build_vertical_video([invalid_video, valid_video])

    assert result == "/tmp/final_vertical.mp4"
    downloader_instance.download_video.assert_awaited_once_with([valid_video])
    worker_factory_instance.start_vertical_workers.assert_called_once_with([valid_video])
    compositor_instance.join_processed_videos.assert_awaited_once_with(video_id_list=["abc123"], vertical=True)


@pytest.mark.asyncio
async def test_vertical_pipeline_raises_when_all_video_ids_are_invalid() -> None:
    settings = AppSettings(yt_search_region_code="ES")
    adapter = VerticalVideoPipelineAdapter(settings)

    with pytest.raises(ValueError, match="No videos with valid video_id"):
        await adapter.build_vertical_video([Video(video_id=" "), Video(video_id="")])


@pytest.mark.asyncio
async def test_horizontal_pipeline_filters_invalid_video_ids() -> None:
    settings = AppSettings(yt_search_region_code="ES")
    adapter = HorizontalVideoPipelineAdapter(settings)
    invalid_video = Video(video_id="")
    valid_video = Video(video_id="xyz789")

    downloader_instance = Mock()
    downloader_instance.video_yt_resources_folder = "videos/yt"
    downloader_instance.download_video = AsyncMock()

    worker_factory_instance = Mock()
    compositor_instance = Mock()
    compositor_instance.join_processed_videos = AsyncMock(return_value="/tmp/final_horizontal.mp4")
    thumbnail_instance = Mock()
    thumbnail_instance.generate_thumbnail = AsyncMock(return_value="/tmp/thumb.png")

    with (
        patch("src.adapters.horizontal_video_pipeline.VideoDownloader", return_value=downloader_instance),
        patch("src.adapters.horizontal_video_pipeline.WorkerFactory", return_value=worker_factory_instance),
        patch("src.adapters.horizontal_video_pipeline.VideoAssetManager", return_value=SimpleNamespace()),
        patch("src.adapters.horizontal_video_pipeline.VideoRenderer", return_value=SimpleNamespace()),
        patch("src.adapters.horizontal_video_pipeline.VideoCompositor", return_value=compositor_instance),
        patch("src.adapters.horizontal_video_pipeline.ThumbnailGenerator", return_value=thumbnail_instance),
    ):
        result = await adapter.build_horizontal_video([invalid_video, valid_video])

    assert result == ("/tmp/final_horizontal.mp4", "/tmp/thumb.png")
    downloader_instance.download_video.assert_awaited_once_with([valid_video])
    worker_factory_instance.start_workers.assert_called_once_with([valid_video])
    compositor_instance.join_processed_videos.assert_awaited_once_with(["xyz789"])
    thumbnail_instance.generate_thumbnail.assert_awaited_once_with([valid_video])


@pytest.mark.asyncio
async def test_horizontal_pipeline_raises_when_all_video_ids_are_invalid() -> None:
    settings = AppSettings(yt_search_region_code="ES")
    adapter = HorizontalVideoPipelineAdapter(settings)

    with pytest.raises(ValueError, match="No videos with valid video_id"):
        await adapter.build_horizontal_video([Video(video_id=""), Video(video_id="   ")])
