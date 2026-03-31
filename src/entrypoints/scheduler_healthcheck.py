"""Healthcheck command for the persistent scheduler."""

from pathlib import Path

from src.config.settings import get_app_settings
from src.entrypoints.scheduler import _heartbeat_is_fresh


def main() -> None:
    settings = get_app_settings()
    is_healthy = _heartbeat_is_fresh(
        heartbeat_file=Path(settings.scheduler_heartbeat_file),
        stale_seconds=settings.scheduler_heartbeat_stale_seconds,
    )
    if not is_healthy:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
