"""TinyDB-backed token cache compatible with Spotipy cache handler API."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

from spotipy.cache_handler import CacheHandler
from tinydb import TinyDB

if TYPE_CHECKING:
    from pathlib import Path


class TinyDBCacheHandler(CacheHandler):
    """Persist Spotipy token info in TinyDB with thread-safe access."""

    def __init__(self, db_path: Path, table: str = "spotify_oauth") -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = TinyDB(str(db_path))
        self._table = self._db.table(table)
        self._lock = threading.Lock()

    def get_cached_token(self) -> dict[str, Any] | None:
        with self._lock:
            docs = self._table.all()
            return docs[0] if docs else None

    def save_token_to_cache(self, token_info: dict[str, Any]) -> None:
        with self._lock:
            self._table.truncate()
            self._table.insert(token_info)

    def clear_cache(self) -> None:
        with self._lock:
            self._table.truncate()
