"""Unit tests for execution lock."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from src.shared.execution_lock import FileExecutionLock


def test_read_lock_state_returns_none_when_file_missing() -> None:
    result = FileExecutionLock.read_lock_state("/nonexistent/lock/file.lock")
    assert result is None


def test_read_lock_state_returns_metadata_when_file_exists() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".lock", delete=False) as f:
        data = {"operation": "test_op", "pid": 1234, "acquired_at": "2026-05-16T10:00:00"}
        json.dump(data, f)
        path = f.name

    try:
        result = FileExecutionLock.read_lock_state(path)
        assert result is not None
        assert result["operation"] == "test_op"
        assert result["pid"] == 1234
    finally:
        Path(path).unlink()


def test_read_lock_state_returns_none_for_empty_file() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".lock", delete=False) as f:
        path = f.name

    try:
        result = FileExecutionLock.read_lock_state(path)
        assert result is None
    finally:
        Path(path).unlink()


def test_read_lock_state_returns_none_for_invalid_json() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".lock", delete=False) as f:
        f.write("not json")
        path = f.name

    try:
        result = FileExecutionLock.read_lock_state(path)
        assert result is None
    finally:
        Path(path).unlink()


def test_lock_file_deleted_on_release() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_path = Path(tmpdir) / "test.lock"
        with FileExecutionLock(lock_path, "test_op") as lock:
            assert lock.acquired is True
            assert lock_path.exists()

        assert not lock_path.exists()


def test_lock_not_acquired_when_already_held() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_path = Path(tmpdir) / "test.lock"
        with FileExecutionLock(lock_path, "test_op") as lock1:
            assert lock1.acquired is True
            with FileExecutionLock(lock_path, "test_op2") as lock2:
                assert lock2.acquired is False
