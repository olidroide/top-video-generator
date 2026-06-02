"""Authentication token storage repository (TinyDB backend)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tinydb import Query, TinyDB

from src.domain.models import TikTokAuth, YtAuth
from src.shared.logging import get_logger

if TYPE_CHECKING:
    from pathlib import Path

logger = get_logger(__name__)


class AuthenticationRepository:
    """
    Manages OAuth2 authentication tokens for third-party integrations.

    Platforms: TikTok, YouTube
    Storage: TinyDB (JSON)
    """

    _TABLE_TIKTOK = "tiktok_auth"
    _TABLE_YT = "yt_auth"

    def __init__(self, db_path: Path) -> None:
        """Initialize repository with TinyDB backend."""
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = TinyDB(str(db_path))

    # ========================================================================
    # TikTok Authentication
    # ========================================================================

    def get_tiktok_auth(self, client_id: str) -> TikTokAuth | None:
        """Retrieve TikTok auth by client_id."""
        table = self._db.table(self._TABLE_TIKTOK)
        results = table.search(Query().client_id == client_id)
        if not results:
            return None
        return TikTokAuth.model_validate(results[0])

    def update_tiktok_auth(self, tiktok_auth: TikTokAuth) -> TikTokAuth:
        """Update TikTok auth for existing client."""
        table = self._db.table(self._TABLE_TIKTOK)
        client_id = tiktok_auth.client_id or ""
        table.update(tiktok_auth.model_dump(), Query().client_id == client_id)
        return tiktok_auth

    def add_or_update_tiktok_auth(self, tiktok_auth: TikTokAuth) -> TikTokAuth:
        """Insert or update TikTok auth (upsert)."""
        client_id = tiktok_auth.client_id or ""
        table = self._db.table(self._TABLE_TIKTOK)
        table.upsert(tiktok_auth.model_dump(), Query().client_id == client_id)
        return tiktok_auth

    # ========================================================================
    # YouTube Authentication
    # ========================================================================

    def get_yt_auth(self, client_id: str) -> YtAuth | None:
        """Retrieve YouTube auth by client_id."""
        table = self._db.table(self._TABLE_YT)
        results = table.search(Query().client_id == client_id)
        if not results:
            return None
        return YtAuth.model_validate(results[0])

    def update_yt_auth(self, yt_auth: YtAuth) -> YtAuth:
        """Update YouTube auth for existing client."""
        table = self._db.table(self._TABLE_YT)
        client_id = yt_auth.client_id or ""
        table.update(yt_auth.model_dump(), Query().client_id == client_id)
        return yt_auth

    def add_or_update_yt_auth(self, yt_auth: YtAuth) -> YtAuth:
        """Insert or update YouTube auth (upsert)."""
        client_id = yt_auth.client_id or ""
        table = self._db.table(self._TABLE_YT)
        table.upsert(yt_auth.model_dump(), Query().client_id == client_id)
        return yt_auth

    def close(self) -> None:
        """Close database connection."""
        self._db.close()
