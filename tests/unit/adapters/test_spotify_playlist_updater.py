from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.adapters.spotify_playlist_updater import SpotifyPlaylistUpdaterAdapter


@pytest.mark.asyncio
async def test_spotify_playlist_updater_delegates_is_authorized() -> None:
    fake_client = AsyncMock()
    fake_client.is_authorized.return_value = True
    adapter = SpotifyPlaylistUpdaterAdapter(fake_client)

    result = await adapter.is_authorized()

    assert result is True
    fake_client.is_authorized.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_spotify_playlist_updater_delegates_update_original_playlist() -> None:
    fake_client = AsyncMock()
    fake_client.update_link_original_playlist.return_value = True
    adapter = SpotifyPlaylistUpdaterAdapter(fake_client)

    result = await adapter.update_original_playlist("playlist_1", ["Song A", "Song B"])

    assert result is True
    fake_client.update_link_original_playlist.assert_awaited_once_with(
        playlist_id="playlist_1",
        song_title_list=["Song A", "Song B"],
    )
