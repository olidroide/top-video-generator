from __future__ import annotations

from src.infrastructure.storage.spotify_token_cache import TinyDBCacheHandler


def test_tinydb_cache_handler_save_get_clear(tmp_path) -> None:
    cache_path = tmp_path / "auth.json"
    cache = TinyDBCacheHandler(cache_path)

    assert cache.get_cached_token() is None

    token = {"access_token": "abc", "refresh_token": "ref", "scope": "playlist-modify-private"}
    cache.save_token_to_cache(token)

    assert cache.get_cached_token() == token

    cache.clear_cache()
    assert cache.get_cached_token() is None
