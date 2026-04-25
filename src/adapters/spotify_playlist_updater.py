"""Adapter for updating Spotify original playlist links."""

from __future__ import annotations

from typing import Protocol

from src.domain.ports import SpotifyPlaylistUpdater


class _SpotifyPlaylistClient(Protocol):
    async def update_link_original_playlist(
        self,
        playlist_id: str | None = None,
        song_title_list: list[str] | None = None,
    ) -> bool: ...


class SpotifyPlaylistUpdaterAdapter(SpotifyPlaylistUpdater):
    """Bridge Spotify playlist update workflow to domain port."""

    def __init__(self, client: _SpotifyPlaylistClient) -> None:
        self._client = client

    async def update_original_playlist(self, playlist_id: str, song_title_list: list[str]) -> bool:
        return await self._client.update_link_original_playlist(
            playlist_id=playlist_id,
            song_title_list=song_title_list,
        )
