"""Advisory file locks for single-host job serialization."""

from __future__ import annotations

import fcntl
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Self, TextIO

from src.shared.logging import get_logger

logger = get_logger(__name__)


class FileExecutionLock:
    def __init__(self, path: str | os.PathLike[str], operation_name: str) -> None:
        self._path = Path(path)
        self._operation_name = operation_name
        self._handle: TextIO | None = None
        self.acquired = False

    def __enter__(self) -> Self:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self._path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            logger.info(
                "execution_lock.busy",
                lock_path=str(self._path),
                operation=self._operation_name,
            )
            self._handle.close()
            self._handle = None
            self.acquired = False
            return self

        self.acquired = True
        self._write_metadata()
        logger.info(
            "execution_lock.acquired",
            lock_path=str(self._path),
            operation=self._operation_name,
        )
        return self

    def __exit__(self, exc_type: object, exc: object, exc_tb: object) -> bool:
        self.release()
        return False

    def release(self) -> None:
        if self._handle is None:
            return
        try:
            if self.acquired:
                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
                logger.info(
                    "execution_lock.released",
                    lock_path=str(self._path),
                    operation=self._operation_name,
                )
        finally:
            self._handle.close()
            self._handle = None
            self.acquired = False
            self._path.unlink(missing_ok=True)

    def _write_metadata(self) -> None:
        if self._handle is None:
            return
        self._handle.seek(0)
        self._handle.truncate()
        self._handle.write(
            json.dumps(
                {
                    "operation": self._operation_name,
                    "pid": os.getpid(),
                    "acquired_at": datetime.now(UTC).isoformat(),
                }
            )
        )
        self._handle.flush()

    @staticmethod
    def read_lock_state(path: str | os.PathLike[str]) -> dict | None:
        """Read lock metadata without acquiring. Returns None if no lock held."""
        lock_path = Path(path)
        if not lock_path.exists():
            return None
        try:
            content = lock_path.read_text(encoding="utf-8").strip()
            if not content:
                return None
            return json.loads(content)
        except (json.JSONDecodeError, OSError):
            return None
