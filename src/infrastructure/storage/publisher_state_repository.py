"""Publisher enable/disable state repository (TinyDB backend)."""

from __future__ import annotations

from pathlib import Path

from tinydb import Query, TinyDB

from src.domain.ports import PublisherStateReader, PublisherStateWriter


class PublisherStateRepository(PublisherStateReader, PublisherStateWriter):
    """Persist publisher enabled state per platform."""

    _TABLE = "publisher_state"
    _DEFAULT_ENABLED = True

    def __init__(self, db_path: str) -> None:
        db_file = Path(db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        self._db = TinyDB(db_path)

    def is_enabled(self, platform: str) -> bool:
        table = self._db.table(self._TABLE)
        result = table.search(Query().platform == platform)
        if not result:
            return self._DEFAULT_ENABLED
        return result[0].get("enabled", self._DEFAULT_ENABLED)

    def set_enabled(self, platform: str, enabled: bool) -> None:
        table = self._db.table(self._TABLE)
        table.upsert({"platform": platform, "enabled": enabled}, Query().platform == platform)

    def get_all(self) -> dict[str, bool]:
        table = self._db.table(self._TABLE)
        records = table.all()
        return {r["platform"]: r["enabled"] for r in records}

    def close(self) -> None:
        self._db.close()
