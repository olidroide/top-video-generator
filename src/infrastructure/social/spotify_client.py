import asyncio
import random
import string
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from importlib import import_module
from typing import TYPE_CHECKING, Any

import aiohttp

from src.config.settings import AppSettings, get_app_settings
from src.domain.models import SpotifyAuth
from src.infrastructure.social.spotipy_exceptions import (
    SpotifyApiError,
    SpotifyAuthError,
    SpotifyClientError,
    SpotifyPermissionError,
    map_spotipy_exception,
)
from src.infrastructure.social.ssl_context_factory import (
    build_ssl_context,
    configure_process_wide_certifi_bundle,
)
from src.shared.logging import get_logger

if TYPE_CHECKING:
    SpotipyFreeSpotify = Any

logger = get_logger(__name__)
HTTP_ERROR_STATUS_CODE = 400
HTTP_NOT_IMPLEMENTED_STATUS_CODE = 501
SPOTIFY_OAUTH_SCOPE = " ".join(
    (
        "user-read-private",
        "user-read-email",
        "playlist-modify-public",
        "playlist-modify-private",
        "playlist-read-private",
        "ugc-image-upload",
    )
)
_SPOTIFYFREE_OAUTH_UNSUPPORTED = "spotipyFree does not support Spotify OAuth or token refresh flows in this project"
_SPOTIFYFREE_PLAYLIST_WRITE_UNSUPPORTED = "spotipyFree does not support authenticated playlist write operations"
_SPOTIFY_OPTIONAL_DEPENDENCY_HINT = (
    "Install Spotify support with `uv sync --extra spotify` or `pip install .[spotify]`."
)


def _load_spotipyfree_spotify_class() -> type["SpotipyFreeSpotify"]:
    try:
        module = import_module("SpotipyFree")
    except ModuleNotFoundError as exc:
        message = f"Spotify optional dependencies are not installed. {_SPOTIFY_OPTIONAL_DEPENDENCY_HINT}"
        if exc.name:
            message = f"{message} Missing module: {exc.name}."
        raise SpotifyClientError(message) from exc

    spotify_class = getattr(module, "Spotify", None)
    if spotify_class is None:
        raise SpotifyClientError(
            "Spotify optional dependency is installed but does not expose SpotipyFree.Spotify. "
            f"{_SPOTIFY_OPTIONAL_DEPENDENCY_HINT}"
        )

    return spotify_class


@asynccontextmanager
async def get_default_client(settings: AppSettings | None = None) -> AsyncIterator[aiohttp.ClientSession]:
    resolved_settings = settings if settings is not None else get_app_settings()
    ssl_context = build_ssl_context(resolved_settings)
    conn = aiohttp.TCPConnector(ssl=ssl_context)
    async with aiohttp.ClientSession(
        connector=conn,
        timeout=aiohttp.ClientTimeout(total=30),
    ) as client:
        yield client


class SpotifyClient:
    _base_url = ""

    def __init__(self, settings: AppSettings | None = None) -> None:
        super().__init__()
        resolved_settings = settings if settings is not None else get_app_settings()
        self._settings = resolved_settings
        self._client_id: str = resolved_settings.spotify_client_id or ""
        self._client_secret: str = resolved_settings.spotify_client_secret or ""
        self._redirect_uri: str = resolved_settings.spotify_redirect_uri or ""
        self._user_id: str = resolved_settings.spotify_user_id or ""
        configure_process_wide_certifi_bundle(resolved_settings)

    @staticmethod
    def _split_scope(scope_value: str | list[str] | None) -> list[str]:
        if isinstance(scope_value, list):
            return scope_value
        if isinstance(scope_value, str) and scope_value:
            return scope_value.split(" ")
        return []

    async def _run_spotipy_call(self, fn: Callable[[], Any]) -> Any:
        try:
            return await asyncio.to_thread(fn)
        except Exception as exc:
            raise map_spotipy_exception(exc) from exc

    def _build_spotify_client(self) -> "SpotipyFreeSpotify":
        spotify_class = _load_spotipyfree_spotify_class()
        return spotify_class()

    async def step_1_get_authentication_url(self) -> str:
        _seed = 36
        random_code = "".join(
            random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(_seed)
        )
        logger.warning(
            "spotify_client.oauth_not_supported",
            state_hint=random_code.lower()[16:],
            reason=_SPOTIFYFREE_OAUTH_UNSUPPORTED,
        )
        return ""

    async def step_2_exchange_code_authentication(
        self,
        authorization_value: str,
    ) -> SpotifyAuth:
        del authorization_value
        raise SpotifyAuthError(_SPOTIFYFREE_OAUTH_UNSUPPORTED)

    async def refresh_token(self) -> str:
        logger.warning("spotify_client.oauth_refresh_not_supported", reason=_SPOTIFYFREE_OAUTH_UNSUPPORTED)
        return ""

    async def fetch_user_info(
        self,
        user_access_token: str | None = None,
    ) -> dict[str, Any]:
        del user_access_token
        try:
            spotify_client = self._build_spotify_client()
            await self._run_spotipy_call(lambda: spotify_client.search(query="test", type="track", limit=1))
            response_dict: dict[str, Any] = {"id": self._user_id or "spotipyfree-public"}
        except SpotifyClientError:
            raise
        except Exception as exc:
            logger.warning("spotify_client.fetch_user_info_failed", error=str(exc))
            raise SpotifyApiError(status_code=None, detail=str(exc)) from exc

        logger.debug("response_dict:", response_dict=response_dict)
        return response_dict

    async def check_connection(self) -> dict[str, Any]:
        try:
            return await self.fetch_user_info()
        except (SpotifyClientError, aiohttp.ClientConnectorError, aiohttp.ClientConnectorCertificateError) as exc:
            return {"error": {"status": HTTP_ERROR_STATUS_CODE, "message": str(exc)}}

    async def is_authorized(self) -> bool:
        user_info = await self.check_connection()
        return isinstance(user_info.get("id"), str)

    async def search_for_track(
        self,
        title_song: str | None = None,
    ) -> dict[str, Any]:
        spotify_client = self._build_spotify_client()
        response_dict = await self._run_spotipy_call(
            lambda: spotify_client.search(query=title_song or "", type="track", limit=1)
        )
        logger.debug("search_for_track response_dict:", response_dict=response_dict)
        tracks = response_dict.get("tracks", {}).get("items", [])
        if not tracks:
            return {}
        return tracks[0]

    async def get_playlist_items_track_id(
        self,
        playlist_id: str | None = None,
    ) -> list[str]:
        spotify_client = self._build_spotify_client()
        response_dict = await self._run_spotipy_call(
            lambda: spotify_client.playlist_items(
                playlist_id or "",
                limit=50,
            )
        )

        logger.debug("get_playlist_items_track_id response_dict:", response_dict=response_dict)
        return [item.get("track", {}).get("id") for item in response_dict.get("items", []) if item.get("track")]

    async def remove_playlist_items(
        self,
        playlist_id: str | None = None,
        item_track_id_list: list[str] | None = None,
    ) -> dict[str, Any]:
        del playlist_id
        del item_track_id_list
        logger.warning(
            "spotify_client.playlist_write_not_supported",
            operation="remove_playlist_items",
            reason=_SPOTIFYFREE_PLAYLIST_WRITE_UNSUPPORTED,
        )
        return {
            "error": {
                "status": HTTP_NOT_IMPLEMENTED_STATUS_CODE,
                "message": _SPOTIFYFREE_PLAYLIST_WRITE_UNSUPPORTED,
            }
        }

    async def add_items_to_playlist(
        self,
        playlist_id: str | None = None,
        track_id_list: list[str] | None = None,
    ) -> dict[str, Any]:
        del playlist_id
        del track_id_list
        logger.warning(
            "spotify_client.playlist_write_not_supported",
            operation="add_items_to_playlist",
            reason=_SPOTIFYFREE_PLAYLIST_WRITE_UNSUPPORTED,
        )
        return {
            "error": {
                "status": HTTP_NOT_IMPLEMENTED_STATUS_CODE,
                "message": _SPOTIFYFREE_PLAYLIST_WRITE_UNSUPPORTED,
            }
        }

    async def update_link_original_playlist(
        self,
        playlist_id: str | None = None,
        song_title_list: list[str] | None = None,
    ) -> bool:
        spotify_tracks_id: list[str] = []
        for yt_video_title in song_title_list or []:
            spotify_track = await self.search_for_track(yt_video_title)
            track_id = spotify_track.get("id")
            if isinstance(track_id, str):
                spotify_tracks_id.append(track_id)
        response_dict = await self.add_items_to_playlist(
            playlist_id=playlist_id,
            track_id_list=spotify_tracks_id,
        )
        if isinstance(response_dict.get("error"), dict):
            raise SpotifyPermissionError(_SPOTIFYFREE_PLAYLIST_WRITE_UNSUPPORTED)
        return True
