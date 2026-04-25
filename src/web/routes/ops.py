"""Operational routes such as health and metrics."""

import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, HTTPException

from src.config.settings import AppSettings
from src.web.dependencies import AppSettingsDep, TimeSeriesRepositoryDep
from src.web.state import HealthCheck, MetricsResponse, metrics_state

router = APIRouter()


def check_ffmpeg() -> dict[str, str]:
    """Check if ffmpeg is available."""
    try:
        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path:
            return {"status": "error", "message": "ffmpeg not found"}

        result = subprocess.run(  # noqa: S603
            [ffmpeg_path, "-version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return {
            "status": "ok" if result.returncode == 0 else "error",
            "message": "ffmpeg available" if result.returncode == 0 else "ffmpeg error",
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "message": f"ffmpeg not found: {exc}"}


def check_templates(settings: AppSettings) -> dict[str, str]:
    """Check if required template files exist."""
    required_files = [
        settings.video_template_file,
        settings.video_template_vertical_file,
        settings.video_template_thumbnail_file,
        settings.video_template_thumbnail_font_file,
    ]

    required_paths = [file_path for file_path in required_files if file_path]
    missing = [file_path for file_path in required_paths if not Path(file_path).exists()]

    return {
        "status": "ok" if not missing else "error",
        "message": "All templates present" if not missing else f"Missing templates: {missing}",
    }


def check_database(timeseries_repo: TimeSeriesRepositoryDep) -> dict[str, str]:
    """Check database connectivity."""
    try:
        _ = timeseries_repo.get_video_points_by_date_range(datetime.now(UTC) - timedelta(days=1), datetime.now(UTC))
        return {"status": "ok", "message": "Database accessible"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "message": f"Database error: {exc}"}


@router.get("/health")
async def health_check(timeseries_repo: TimeSeriesRepositoryDep, settings: AppSettingsDep) -> HealthCheck:
    """Health check endpoint for monitoring."""
    checks = {
        "ffmpeg": check_ffmpeg(),
        "templates": check_templates(settings),
        "database": check_database(timeseries_repo),
    }

    overall_status = "healthy" if all(check["status"] == "ok" for check in checks.values()) else "unhealthy"
    return HealthCheck(status=overall_status, checks=checks)


@router.get("/metrics")
async def metrics() -> MetricsResponse:
    """Metrics endpoint for monitoring."""
    return MetricsResponse(**metrics_state)


@router.post("/metrics/increment/{metric_name}")
async def increment_metric(metric_name: str, error: bool = False) -> dict[str, str]:
    """Internal endpoint to increment metrics (used by background tasks)."""
    allowed_metrics = {name.rsplit("_", maxsplit=1)[0] for name in metrics_state}
    if metric_name not in allowed_metrics:
        raise HTTPException(status_code=400, detail=f"Invalid metric: {metric_name}")

    key = f"{metric_name}_errors" if error else f"{metric_name}_count"
    if key in metrics_state:
        metrics_state[key] += 1
    return {"status": "ok"}
