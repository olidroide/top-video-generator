"""Tests for shared path utilities."""

from __future__ import annotations

from pathlib import Path

from src.config.settings import PROJECT_ROOT
from src.shared.utils import resolve_project_path


def test_resolve_project_path_with_absolute_path() -> None:
    """Absolute paths should be returned unchanged."""
    abs_path = Path("/var/lib/some/data.json")
    result = resolve_project_path(str(abs_path))
    assert result == abs_path


def test_resolve_project_path_with_relative_path() -> None:
    """Relative paths should be prefixed with PROJECT_ROOT."""
    rel_path = "db/data.json"
    result = resolve_project_path(rel_path)
    assert result == PROJECT_ROOT / rel_path


def test_resolve_project_path_with_dot_slash_prefix() -> None:
    """Paths with ./ should be resolved relative to PROJECT_ROOT."""
    rel_path = "./db/data.json"
    result = resolve_project_path(rel_path)
    assert result == PROJECT_ROOT / rel_path
