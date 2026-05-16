"""Log file reading utilities for admin panel."""

from __future__ import annotations

import datetime
from pathlib import Path  # noqa: TC003


def read_log_lines_since(log_path: Path, since_timestamp: float | None, max_lines: int) -> list[dict[str, str]]:
    """Read last N lines from log file, optionally filtering by timestamp."""
    try:
        all_lines = log_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    recent = all_lines[-max_lines:] if len(all_lines) > max_lines else all_lines

    if since_timestamp is None:
        return [classify_log_line(line) for line in recent if line.strip()]

    cutoff_str = datetime.datetime.fromtimestamp(since_timestamp, tz=datetime.UTC).strftime("%Y-%m-%d %H:%M:%S")
    return [classify_log_line(line) for line in recent if line.strip() and line[:19] >= cutoff_str]


def classify_log_line(line: str) -> dict[str, str]:
    """Classify a log line by level for color coding."""
    level = "info"
    lower = line.lower()
    if "error" in lower or "exception" in lower or "traceback" in lower or "failed" in lower:
        level = "error"
    elif "warning" in lower or "warn" in lower:
        level = "warning"
    return {"text": line, "level": level}
