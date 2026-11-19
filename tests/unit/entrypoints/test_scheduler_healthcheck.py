from __future__ import annotations

from pathlib import Path

import pytest

from src.entrypoints import scheduler_healthcheck


def test_scheduler_healthcheck_rejects_unhealthy_heartbeat(tmp_path: Path, monkeypatch) -> None:
    heartbeat_file = tmp_path / "scheduler-heartbeat.json"
    heartbeat_file.write_text(
        '{"updated_at":"2026-03-31T12:00:00+00:00","error":"fetch failed"}',
        encoding="utf-8",
    )

    monkeypatch.setattr(
        scheduler_healthcheck,
        "get_app_settings",
        lambda: type(
            "Settings",
            (),
            {
                "scheduler_heartbeat_file": str(heartbeat_file),
                "scheduler_heartbeat_stale_seconds": 10800,
            },
        )(),
    )

    with pytest.raises(SystemExit) as exc_info:
        scheduler_healthcheck.main()
    assert exc_info.value.code == 1
