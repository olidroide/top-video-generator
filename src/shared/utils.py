"""Shared utilities across application layers."""

from __future__ import annotations

from pathlib import Path


def resolve_project_path(path_value: str) -> Path:
    """Resolve a path relative to PROJECT_ROOT if it's not absolute.

    Args:
        path_value: Path string (absolute or relative to PROJECT_ROOT)

    Returns:
        Path: Resolved absolute Path object

    Examples:
        >>> resolve_project_path("/var/data.json")
        Path("/var/data.json")
        >>> resolve_project_path("db/data.json")
        Path("/project/root/db/data.json")
    """
    from src.config.settings import PROJECT_ROOT

    path = Path(path_value)
    return path if path.is_absolute() else PROJECT_ROOT / path
