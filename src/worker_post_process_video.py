import asyncio
import gc
import sys

import zmq

from src.db_client import Video
from src.logger import get_logger
from src.video_processing import VideoProcessing

logger = get_logger(__name__)


def main_main(port, screen_orientation):
    context = zmq.Context()

    # receiver work
    consumer_receiver = context.socket(zmq.PULL)
    consumer_receiver.connect(f"tcp://127.0.0.1:{port}")

    # sender work
    consumer_sender = context.socket(zmq.PUSH)
    consumer_sender.connect("tcp://127.0.0.1:5559")

    map_screen_orientation_process = {
        "vertical": VideoProcessing().post_process_vertical_video,
        "horizontal": VideoProcessing().post_process_video,
    }

    while True:
        logger.debug("listen on port:", port=port)
        video_work_json = consumer_receiver.recv_json()
        logger.debug("Process videos: ", number_of_videos=len(video_work_json))
        for video_json in video_work_json:
            video = Video.model_validate_json(video_json)
            asyncio.run(
                map_screen_orientation_process.get(screen_orientation, VideoProcessing().post_process_video)(video)
            )
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
