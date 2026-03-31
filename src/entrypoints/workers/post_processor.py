"""Video post-processor worker process."""

import asyncio
import gc
import sys

import zmq

from src.config.settings import get_app_settings
from src.domain.models import Video
from src.infrastructure.video.asset_manager import VideoAssetManager
from src.infrastructure.video.compositor import VideoCompositor
from src.infrastructure.video.renderer import VideoRenderer
from src.infrastructure.youtube.downloader import VideoDownloader
from src.shared.logging import get_logger

logger = get_logger(__name__)


def main_main(port: int, screen_orientation: str) -> None:
    context = zmq.Context()

    # receiver work
    consumer_receiver = context.socket(zmq.PULL)
    consumer_receiver.connect(f"tcp://127.0.0.1:{port}")

    # sender work
    consumer_sender = context.socket(zmq.PUSH)
    consumer_sender.connect("tcp://127.0.0.1:5559")

    settings = get_app_settings()
    downloader = VideoDownloader()
    asset_manager = VideoAssetManager(
        end_screen_file=settings.video_template_end_screen_file or "",
        start_screen_file=settings.video_template_start_screen_file or "",
        template_file=settings.video_template_file or "",
        template_vertical_file=settings.video_template_vertical_file or "",
        thumbnail_file=settings.video_template_thumbnail_file or "",
        thumbnail_font_file=settings.video_template_thumbnail_font_file or "",
        video_yt_resources_folder=downloader.video_yt_resources_folder,
        video_generated_base_folder=settings.video_generated_folder,
    )
    renderer = VideoRenderer(asset_manager)
    compositor = VideoCompositor(asset_manager, renderer)
    map_screen_orientation_process = {
        "vertical": compositor.post_process_vertical_video,
        "horizontal": compositor.post_process_video,
    }

    while True:
        logger.debug("listen on port:", port=port)
        video_work_json = consumer_receiver.recv_json()
        logger.debug("Process videos: ", number_of_videos=len(video_work_json))
        for video_json in video_work_json:
            video = Video.model_validate_json(video_json)
            asyncio.run(map_screen_orientation_process.get(screen_orientation, compositor.post_process_video)(video))
            result = {"video_id": video.video_id}
            consumer_sender.send_json(result)
            gc.collect()
        logger.debug("finish process all the videos, worker exit", number_of_videos=len(video_work_json))
        sys.exit()


if __name__ == "__main__":
    script_name = sys.argv
    arguments = sys.argv[1].strip().split(" ")
    port = int(arguments[0])
    screen_orientation = str(arguments[1])
    main_main(port, screen_orientation)
