from __future__ import annotations

from pathlib import Path

from src.infrastructure.storage.auth_repository import AuthenticationRepository


def test_auth_repository_creates_parent_directory(tmp_path: Path) -> None:
    db_path = tmp_path / "nested" / "auth.json"

    repo = AuthenticationRepository(db_path)
    try:
        assert db_path.parent.exists()
        assert db_path.exists()
    finally:
        repo.close()
