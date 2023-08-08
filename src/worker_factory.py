import os
import pathlib
import subprocess
import sys
from typing import Iterator

import math
import structlog
import zmq
from zmq import Context

from src.db_client import Video
from src.settings import get_app_settings

logger = structlog.get_logger()


class WorkerFactory:
    @staticmethod
    def _create_worker_connection(context: Context, port: int, screen_orientation: str):
        try:
            DIR_PATH = pathlib.Path(__file__).parent
            WORKER_SCRIPT_FILE_PATH = str(DIR_PATH / "worker_post_process_video.py")
            subprocess.Popen(["python", WORKER_SCRIPT_FILE_PATH, f" {port} {screen_orientation}"], shell=False)
        except OSError as e:
            logger.error("Execution failed:", e, file=sys.stderr)

        zmq_socket = context.socket(zmq.PUSH)
        zmq_socket.bind(f"tcp://127.0.0.1:{port}")
        return zmq_socket

    @staticmethod
    def _divide_in_chunks(video_list: list[Video], chunk_size: int) -> Iterator[list[str]]:
        for i in range(0, len(video_list), chunk_size):
            yield [video.json() for video in video_list[i : i + chunk_size]]

    def _wait_workers(
        self,
        video_list: list[Video],
        list_worker,
        context,
        results_receiver,
    ):
        videos_per_worker = math.ceil(len(video_list) / len(list_worker))
        for index, videos_to_send in enumerate(self._divide_in_chunks(video_list, videos_per_worker)):
            list_worker[index].send_json(videos_to_send)
        finished_video_id_list = []
        while len(finished_video_id_list) != len(video_list):
            result = results_receiver.recv_json()
            finished_video_id_list.append(result)
            logger.debug(
                f"finish ({len(finished_video_id_list)} of {len(video_list)} )",
                result=result,
            )
        context.destroy()

    def _start_workers(self, video_list: list[Video], screen_orientation: str):
        context = zmq.Context()
        results_receiver = context.socket(zmq.PULL)
        results_receiver.bind("tcp://127.0.0.1:5559")
        list_worker = []

        if not (cpu_count := get_app_settings().cpu_workers):
            cpu_count = math.ceil(os.cpu_count()) - 2

        cpu_count = cpu_count if cpu_count > 0 else 1

        for i in range(cpu_count):
            port = 5570 + i
            list_worker.append(self._create_worker_connection(context, port, screen_orientation))

        self._wait_workers(
            video_list=video_list,
            list_worker=list_worker,
            context=context,
            results_receiver=results_receiver,
        )

    def start_workers(self, video_list: list[Video]):
        self._start_workers(video_list=video_list, screen_orientation="horizontal")

    def start_vertical_workers(self, video_list: list[Video]):
        self._start_workers(video_list=video_list, screen_orientation="vertical")
