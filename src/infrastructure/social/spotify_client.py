import asyncio
import os
import random
import string
from base64 import urlsafe_b64encode
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import aiohttp
import requests
import spotipy
from requests.exceptions import RequestException
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyOAuth

from src.config.settings import AppSettings, get_app_settings
from src.domain.models import SpotifyAuth
from src.infrastructure.social.spotipy_exceptions import SpotifyClientError, map_spotipy_exception
from src.infrastructure.social.ssl_context_factory import build_ssl_context, configure_process_wide_certifi_bundle
from src.infrastructure.storage.auth_repository import AuthenticationRepository
from src.infrastructure.storage.spotify_token_cache import TinyDBCacheHandler
from src.shared.logging import get_logger

logger = get_logger(__name__)
HTTP_ERROR_STATUS_CODE = 400
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
        self._db_auth_file: str = resolved_settings.db_auth_file
        cert_bundle = configure_process_wide_certifi_bundle(resolved_settings)
        requests_session = requests.Session()
        if cert_bundle:
            requests_session.verify = cert_bundle
            logger.info("spotify_client.requests_ca_bundle_enabled", cert_bundle=cert_bundle)

        self._cache_handler = TinyDBCacheHandler(Path(self._db_auth_file))
        self._oauth_manager = SpotifyOAuth(
            client_id=self._client_id,
            client_secret=self._client_secret,
            redirect_uri=self._redirect_uri,
            scope=SPOTIFY_OAUTH_SCOPE,
            open_browser=False,
            requests_session=requests_session,
            requests_timeout=30,
            cache_handler=self._cache_handler,
        )

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
        except SpotifyException as exc:
            raise map_spotipy_exception(exc) from exc
        except RequestException as exc:
            raise map_spotipy_exception(exc) from exc

    def _build_spotify_client(self, access_token: str | None = None) -> spotipy.Spotify:
        if access_token:
            return spotipy.Spotify(auth=access_token, requests_timeout=30)
        return spotipy.Spotify(auth_manager=self._oauth_manager, requests_timeout=30)

    def _get_access_token_info_sync(self) -> dict[str, Any] | None:
        token_info = self._oauth_manager.get_cached_token()
        if token_info:
            return token_info

        refresh_token = self._get_user_refresh_token_sync()
        if not refresh_token:
            return None

        refreshed = self._oauth_manager.refresh_access_token(refresh_token)
        self._cache_handler.save_token_to_cache(refreshed)
        return refreshed

    def _exchange_code_for_token_info_sync(self, authorization_value: str) -> dict[str, Any]:
        try:
            response = self._oauth_manager.get_access_token(
                authorization_value,
                as_dict=True,
                check_cache=False,
            )
        except TypeError:
            response = self._oauth_manager.get_access_token(authorization_value)

        if isinstance(response, str):
            return {"access_token": response}
        if isinstance(response, dict):
            return response
        return {}

    def _get_user_refresh_token_sync(self) -> str:
        repo = AuthenticationRepository(Path(self._db_auth_file))
        spotify_auth = repo.get_spotify_auth(self._user_id)
        if spotify_auth is None:
            return ""
        return spotify_auth.refresh_token or ""

    async def _get_user_refresh_token(self) -> str:
        return await asyncio.to_thread(self._get_user_refresh_token_sync)

    async def _get_user_access_token(self) -> str:
        return await self.refresh_token()

    def _get_app_token_bearer_credentials(self) -> str:
        return urlsafe_b64encode(f"{self._client_id}:{self._client_secret}".encode("ascii")).decode("ascii")

    async def step_1_get_authentication_url(self) -> str:
        _seed = 36
        random_code = "".join(
            random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(_seed)
        )
        state = random_code.lower()[16:]
        request_code_url = await self._run_spotipy_call(lambda: self._oauth_manager.get_authorize_url(state=state))

        logger.debug("url", request_code_url=request_code_url)
        return request_code_url

    async def step_2_exchange_code_authentication(
        self,
        authorization_value: str,
    ) -> SpotifyAuth:
        response_dict = await self._run_spotipy_call(
            lambda: self._exchange_code_for_token_info_sync(authorization_value)
        )

        client_id = self._user_id
        try:
            user_info = await self.fetch_user_info(user_access_token=response_dict.get("access_token"))
            resolved_client_id = user_info.get("id")
            if isinstance(resolved_client_id, str) and resolved_client_id:
                client_id = resolved_client_id
        except SpotifyClientError as exc:
            logger.warning(
                "spotify_client.user_info_unavailable_after_token_exchange",
                error=str(exc),
                fallback_client_id=self._user_id,
            )

        logger.debug("auth token", token_scopes=response_dict.get("scope"), client_id=client_id)
        return SpotifyAuth(
            token=response_dict.get("access_token"),
            refresh_token=response_dict.get("refresh_token"),
            client_id=client_id,
            scopes=self._split_scope(response_dict.get("scope")),
        )

    async def refresh_token(self) -> str:
        response_dict = await self._run_spotipy_call(self._get_access_token_info_sync)
        if not isinstance(response_dict, dict):
            logger.warning("spotify_client.refresh_token_missing_token")
            return ""

        logger.debug("refresh token response", token_scopes=response_dict.get("scope"))
        repo = AuthenticationRepository(Path(self._db_auth_file))
        scopes = self._split_scope(response_dict.get("scope"))
        spotify_auth = repo.add_or_update_spotify_auth(
            spotify_auth=SpotifyAuth(
                token=response_dict.get("access_token"),
                refresh_token=response_dict.get("refresh_token") or await self._get_user_refresh_token(),
                client_id=self._user_id,
                scopes=scopes,
            )
        )
        return spotify_auth.token or ""

    async def fetch_user_info(
        self,
        user_access_token: str | None = None,
    ) -> dict[str, Any]:
        try:
            spotify_client = self._build_spotify_client(user_access_token)
            response_dict = await self._run_spotipy_call(spotify_client.me)
        except aiohttp.ClientConnectorCertificateError as exc:
            logger.exception(
                "spotify_client.ssl_certificate_verification_failed",
                host=getattr(exc, "host", None),
                port=getattr(exc, "port", None),
                ssl_cert_file=os.environ.get("SSL_CERT_FILE"),
                requests_ca_bundle=os.environ.get("REQUESTS_CA_BUNDLE"),
                use_certifi=self._settings.use_certifi,
            )
            raise
        except aiohttp.ClientConnectorError as exc:
            logger.exception(
                "spotify_client.connection_failed",
                host=getattr(exc, "host", None),
                port=getattr(exc, "port", None),
                ssl_cert_file=os.environ.get("SSL_CERT_FILE"),
                requests_ca_bundle=os.environ.get("REQUESTS_CA_BUNDLE"),
                use_certifi=self._settings.use_certifi,
            )
            raise
        except Exception as exc:
            logger.warning("spotify_client.fetch_user_info_failed", error=str(exc))
            raise

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
        access_token = await self._get_user_access_token()
        spotify_client = self._build_spotify_client(access_token)
        response_dict = await self._run_spotipy_call(
            lambda: spotify_client.search(q=title_song or "", type="track", limit=1)
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
        access_token = await self._get_user_access_token()
        spotify_client = self._build_spotify_client(access_token)
        response_dict = await self._run_spotipy_call(
            lambda: spotify_client.playlist_items(
                playlist_id=playlist_id or "",
                fields="items(track(id))",
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
        track_id_list = item_track_id_list or []
        access_token = await self._get_user_access_token()
        spotify_client = self._build_spotify_client(access_token)
        item_uris = [f"spotify:track:{item_track_id}" for item_track_id in track_id_list]
        response_dict = await self._run_spotipy_call(
            lambda: spotify_client.playlist_remove_all_occurrences_of_items(
                playlist_id or "",
                item_uris,
            )
        )

        logger.debug("remove_playlist_items response_dict:", response_dict=response_dict)
        return response_dict

    async def add_items_to_playlist(
        self,
        playlist_id: str | None = None,
        track_id_list: list[str] | None = None,
    ) -> dict[str, Any]:
        access_token = await self._get_user_access_token()
        spotify_client = self._build_spotify_client(access_token)
        track_uris = [f"spotify:track:{track_id}" for track_id in (track_id_list or [])]
        response_dict = await self._run_spotipy_call(
            lambda: spotify_client.playlist_replace_items(
                playlist_id or "",
                track_uris,
            )
        )

        logger.debug("add_items_to_playlist response_dict:", response_dict=response_dict)
        if isinstance(response_dict, dict):
            return response_dict
        return {}

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
        await self.add_items_to_playlist(
            playlist_id=playlist_id,
            track_id_list=spotify_tracks_id,
        )
        return True
