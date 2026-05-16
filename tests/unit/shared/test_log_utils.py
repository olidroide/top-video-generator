"""Unit tests for log_utils."""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from pathlib import Path

from src.shared.log_utils import classify_log_line, read_log_lines_since


def test_classify_log_line_error() -> None:
    assert classify_log_line("2026-05-16 10:00:00 [error] something failed")["level"] == "error"
    assert classify_log_line("2026-05-16 10:00:00 [info] exception occurred")["level"] == "error"
    assert classify_log_line("2026-05-16 10:00:00 [info] traceback here")["level"] == "error"


def test_classify_log_line_warning() -> None:
    assert classify_log_line("2026-05-16 10:00:00 [warning] disk space low")["level"] == "warning"
    assert classify_log_line("2026-05-16 10:00:00 [info] warn: something")["level"] == "warning"


def test_classify_log_line_info() -> None:
    assert classify_log_line("2026-05-16 10:00:00 [info] all good")["level"] == "info"


def test_read_log_lines_since_no_file() -> None:
    result = read_log_lines_since(Path("/nonexistent/log.log"), None, max_lines=10)
    assert result == []


def test_read_log_lines_since_returns_all_when_no_timestamp() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
        f.write("2026-05-16 10:00:00 [info] line1\n")
        f.write("2026-05-16 10:00:01 [error] line2\n")
        f.write("\n")
        path = f.name

    try:
        result = read_log_lines_since(Path(path), None, max_lines=10)
        assert len(result) == 2
        assert result[0]["level"] == "info"
        assert result[1]["level"] == "error"
    finally:
        Path(path).unlink()


def test_read_log_lines_since_filters_by_timestamp() -> None:
    now = datetime.now(UTC)
    from datetime import timedelta

    old_ts = (now - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
    new_ts = (now - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")
    newer_ts = now.strftime("%Y-%m-%d %H:%M:%S")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
        f.write(f"{old_ts} [info] old line\n")
        f.write(f"{new_ts} [info] new line\n")
        f.write(f"{newer_ts} [error] newer line\n")
        path = f.name

    try:
        cutoff = (now - timedelta(minutes=5)).timestamp()
        result = read_log_lines_since(Path(path), cutoff, max_lines=10)
        assert len(result) == 2
        assert "old line" not in result[0]["text"]
    finally:
        Path(path).unlink()


def test_read_log_lines_since_respects_max_lines() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
        for i in range(100):
            f.write(f"2026-05-16 10:00:{i:02d} [info] line {i}\n")
        path = f.name

    try:
        result = read_log_lines_since(Path(path), None, max_lines=10)
        assert len(result) == 10
        assert "line 90" in result[0]["text"]
        assert "line 99" in result[-1]["text"]
    finally:
        Path(path).unlink()
