"""Atomic file storage with file-level locking.

Provides safe concurrent access to JSON files with:
- Exclusive file locks (fcntl on Unix)
- Atomic writes (tempfile + POSIX rename)
- Graceful error handling and logging
"""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any

from src.shared.logging import get_logger

logger = get_logger(__name__)


class AtomicFileStorage:
    """Atomic JSON file storage with file-level locking.

    Uses fcntl locks (Unix) to serialize writes and tempfile + rename
    pattern to ensure atomic write operations without corruption.
    """

    def __init__(self, file_path: str) -> None:
        """Initialize storage for a JSON file.

        Args:
            file_path: Path to JSON file. Will be created if absent.
        """
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def read_json(self) -> dict[str, Any]:
        """Read JSON file with exclusive lock.

        Returns:
            Parsed JSON dict, or empty dict if file absent or empty.
        """
        if not self.file_path.exists():
            return {}

        try:
            with self.file_path.open(encoding="utf-8") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)  # Shared lock for read
                try:
                    content = f.read()
                    if not content:
                        return {}
                    return json.loads(content)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # Release lock
        except (json.JSONDecodeError, OSError):
            logger.exception("Failed to read JSON from %s", self.file_path)
            return {}

    def write_json(self, data: dict[str, Any]) -> None:
        """Write JSON file atomically with exclusive lock.

        Uses tempfile + POSIX rename pattern for atomicity:
        1. Write to temp file in same directory
        2. Acquire exclusive lock on target file
        3. Rename temp → target (atomic on POSIX)
        4. Release lock

        Args:
            data: Dict to serialize as JSON.
        """
        try:
            # Write to temp file in same directory (ensures same filesystem)
            temp_fd, temp_path = tempfile.mkstemp(
                dir=self.file_path.parent,
                prefix=f".{self.file_path.name}.",
                suffix=".tmp",
            )
            try:
                with os.fdopen(temp_fd, "w", encoding="utf-8") as temp_f:
                    json.dump(data, temp_f, indent=2, ensure_ascii=False)
                    temp_f.flush()
                    os.fsync(temp_f.fileno())  # Ensure written to disk

                # Acquire exclusive lock on target file before rename
                with self.file_path.open("a", encoding="utf-8") as target_f:
                    fcntl.flock(target_f.fileno(), fcntl.LOCK_EX)  # Exclusive lock
                    try:
                        # Atomic rename: temp → target
                        Path(temp_path).rename(self.file_path)
                        logger.debug("Atomically wrote %s", self.file_path)
                    finally:
                        fcntl.flock(target_f.fileno(), fcntl.LOCK_UN)  # Release lock
            except OSError:
                # Clean up temp file on error
                with suppress(OSError):
                    Path(temp_path).unlink()
                raise
        except OSError:
            logger.exception("Failed to write JSON to %s", self.file_path)
            raise

    @contextmanager
    def locked_read_write(self):  # noqa: ANN201
        """Context manager for atomic read-modify-write operations.

        Acquires exclusive lock, yields the current JSON dict, and
        writes back any modifications on exit.

        Example:
            with storage.locked_read_write() as data:
                data['key'] = 'new_value'
                # Auto-written on exit

        Yields:
            Mutable dict that will be written back on successful exit.
        """
        if not self.file_path.exists():
            # Create file with lock if it doesn't exist
            self.file_path.touch()

        try:
            with self.file_path.open("r+", encoding="utf-8") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # Exclusive lock
                try:
                    content = f.read()
                    data: dict[str, Any] = json.loads(content) if content else {}
                    yield data

                    # Write back modified data
                    f.seek(0)
                    f.truncate()
                    json.dump(data, f, indent=2, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())
                    logger.debug("Wrote back locked data to %s", self.file_path)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # Release lock
        except (json.JSONDecodeError, OSError):
            logger.exception("Failed to perform locked read-write on %s", self.file_path)
            raise
