"""Worker process factory for parallel video post-processing."""

import math
import os
import pathlib
import subprocess
import sys
from collections.abc import Iterator
from typing import Any

import zmq
from zmq import Context

from src.config.settings import get_app_settings
from src.domain.models import Video
from src.shared.logging import get_logger

logger = get_logger(__name__)


class WorkerFactory:
    @staticmethod
    def _create_worker_connection(context: Context, port: int, screen_orientation: str) -> Any:
        try:
            dir_path = pathlib.Path(__file__).parent
            worker_script_file_path = str(dir_path / "post_processor.py")
            subprocess.Popen(  # noqa: S603
                [sys.executable, worker_script_file_path, f" {port} {screen_orientation}"],
                shell=False,
            )
        except OSError:
            logger.exception("worker_factory.spawn_failed", port=port, orientation=screen_orientation)

        zmq_socket = context.socket(zmq.PUSH)
        zmq_socket.bind(f"tcp://127.0.0.1:{port}")
        return zmq_socket

    @staticmethod
    def _divide_in_chunks(video_list: list[Video], chunk_size: int) -> Iterator[list[str]]:
        for i in range(0, len(video_list), chunk_size):
            yield [video.model_dump_json() for video in video_list[i : i + chunk_size]]

    def _wait_workers(
        self,
        video_list: list[Video],
        list_worker: list[Any],
        context: Context,
        results_receiver: Any,
    ) -> None:
        videos_per_worker = math.ceil(len(video_list) / len(list_worker))
        for index, videos_to_send in enumerate(self._divide_in_chunks(video_list, videos_per_worker)):
            list_worker[index].send_json(videos_to_send)
        finished_video_id_list = []
        while len(finished_video_id_list) != len(video_list):
            result = results_receiver.recv_json()
            finished_video_id_list.append(result)
            logger.debug(
                "worker_factory.worker_finished",
                completed=len(finished_video_id_list),
                total=len(video_list),
                result=result,
            )
        context.destroy()

    def _start_workers(self, video_list: list[Video], screen_orientation: str) -> None:
        context = zmq.Context()
        results_receiver = context.socket(zmq.PULL)
        results_receiver.bind("tcp://127.0.0.1:5559")
        list_worker = []

        if not (cpu_count := get_app_settings().cpu_workers):
            detected_cpu_count = os.cpu_count() or 1
            cpu_count = math.ceil(detected_cpu_count) - 2

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

    def start_workers(self, video_list: list[Video]) -> None:
        self._start_workers(video_list=video_list, screen_orientation="horizontal")

    def start_vertical_workers(self, video_list: list[Video]) -> None:
        self._start_workers(video_list=video_list, screen_orientation="vertical")
