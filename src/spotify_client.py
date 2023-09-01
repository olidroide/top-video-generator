import json
import random
import string
from base64 import urlsafe_b64encode
from contextlib import asynccontextmanager
from urllib.parse import urlencode

import aiohttp

from src.db_client import DatabaseClient, SpotifyAuth
from src.logger import get_logger
from src.settings import get_app_settings

logger = get_logger(__name__)


@asynccontextmanager
async def get_default_client():
    conn = None
    async with aiohttp.ClientSession(
        connector=conn,
        timeout=aiohttp.ClientTimeout(total=30),
    ) as client:
        yield client


class SpotifyClient:
    _base_url = ""

    def __init__(self) -> None:
        super().__init__()
        self._client_id: str = get_app_settings().spotify_client_id
        self._client_secret: str = get_app_settings().spotify_client_secret
        self._redirect_uri: str = get_app_settings().spotify_redirect_uri
        # self._tiktok_app_id: str = get_app_settings().tiktok_app_id
        self._user_id: str = get_app_settings().spotify_user_id

    async def _get_user_refresh_token(self) -> str:
        tiktok_auth = DatabaseClient().get_spotify_auth(self._user_id)
        return tiktok_auth.refresh_token

    async def _get_user_access_token(self) -> str:
        return await self.refresh_token()
        # tiktok_auth = DatabaseClient().get_spotify_auth(self._user_id)
        # return tiktok_auth.token

    def _get_app_token_bearer_credentials(self) -> str:
        return urlsafe_b64encode(f"{self._client_id}:{self._client_secret}".encode("ascii")).decode("ascii")

    async def step_1_get_authentication_url(self) -> str:
        _seed = 36
        random_code = "".join(
            random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(_seed)
        )
        scope = "user-read-private user-read-email playlist-modify-public playlist-modify-private ugc-image-upload"

        authorize_url = "https://accounts.spotify.com/authorize"
        query_params = {
            "response_type": "code",
            "client_id": self._client_id,
            "scope": scope,
            "redirect_uri": self._redirect_uri,
            "state": random_code.lower()[16:],
        }

        request_code_url = authorize_url + "?" + urlencode(query_params)

        logger.debug("url", request_code_url=request_code_url)
        return request_code_url

    async def step_2_exchange_code_authentication(
        self,
        user_code: str,
    ) -> dict:
        authorize_url = f"https://accounts.spotify.com/api/token"
        data = {
            "code": user_code,
            "grant_type": "authorization_code",
            "redirect_uri": self._redirect_uri,
        }

        headers = {
            "Authorization": f"Basic {self._get_app_token_bearer_credentials()}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Cache-Control": "no-cache",
        }

        async with get_default_client() as client:
            response = await client.post(url=authorize_url, headers=headers, data=data)
            response_dict = await response.json()

        user_info = await self.fetch_user_info(user_access_token=response_dict.get("access_token"))
        response_dict["client_id"] = user_info.get("id")

        logger.debug("auth token:", response_dict=response_dict)
        return response_dict

    async def refresh_token(self) -> str:
        url = f"https://accounts.spotify.com/api/token"
        headers = {
            "Authorization": f"Basic {self._get_app_token_bearer_credentials()}",
        }

        data = {
            "refresh_token": await self._get_user_refresh_token(),
            "grant_type": "refresh_token",
        }

        async with get_default_client() as client:
            response = await client.post(url=url, headers=headers, data=data)
            response_dict = await response.json()

        logger.debug("response_dict:", response_dict=response_dict)
        spotify_auth = DatabaseClient().add_or_update_spotify_auth(
            spotify_auth=SpotifyAuth(
                token=response_dict.get("access_token"),
                # refresh_token=response_dict.get("refresh_token"),
                client_id=self._user_id,
                scopes=response_dict.get("scope", "").split(" "),
            )
        )
        return spotify_auth.token

    async def fetch_user_info(
        self,
        user_access_token: str = None,
    ) -> dict:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {user_access_token or await self._get_user_access_token()}",
        }

        url = "https://api.spotify.com/v1/me/"
        async with get_default_client() as client:
            response = await client.get(url=url, headers=headers)
            response_dict = await response.json()
        logger.debug("response_dict:", response_dict=response_dict)
        # response_dict.get("id")
        return response_dict

    async def search_for_track(
        self,
        title_song: str = None,
    ) -> dict:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {await self._get_user_access_token()}",
        }
        query_params = {
            "q": title_song,
            "type": "track",
            "limit": 1,
        }

        url = f"https://api.spotify.com/v1/search?{urlencode(query_params)}"
        async with get_default_client() as client:
            response = await client.get(url=url, headers=headers)
            response_dict = await response.json()
        logger.debug("search_for_track response_dict:", response_dict=response_dict)
        item_song = response_dict.get("tracks", {}).get("items", [])[0]
        # item_song.get("id")
        return item_song

    async def get_playlist_items_track_id(
        self,
        playlist_id: str = None,
    ) -> list[str]:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {await self._get_user_access_token()}",
        }
        query_params = {
            "playlist_id": playlist_id,
            "fields": "items(track(id))",
            "limit": 50,
        }

        url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks?{urlencode(query_params)}"
        async with get_default_client() as client:
            response = await client.get(url=url, headers=headers)
            response_dict = await response.json()

        logger.debug("get_playlist_items_track_id response_dict:", response_dict=response_dict)
        item_track_id_list = [item.get("track", {}).get("id") for item in response_dict.get("items", [])]
        return item_track_id_list

    async def remove_playlist_items(
        self,
        playlist_id: str = None,
        item_track_id_list: list[str] = None,
    ) -> list[str]:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {await self._get_user_access_token()}",
        }
        data = {"tracks": [{"uri": f"spotify:track:{item_track_id}"} for item_track_id in item_track_id_list]}

        url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
        async with get_default_client() as client:
            response = await client.delete(url=url, headers=headers, data=json.dumps(data))
            response_dict = await response.json()

        logger.debug("remove_playlist_items response_dict:", response_dict=response_dict)
        # return response_dict.get("snapshot_id")
        return response_dict

    async def add_items_to_playlist(
        self,
        playlist_id: str = None,
        track_id_list: list[str] = None,
    ) -> dict:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {await self._get_user_access_token()}",
        }

        data = {
            "position": 0,
            "uris": [f"spotify:track:{track_id}" for track_id in track_id_list],  # TODO limit to 100
        }

        url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
        async with get_default_client() as client:
            response = await client.post(
                url=url,
                headers=headers,
                data=json.dumps(data),
            )
            response_dict = await response.json()

        logger.debug("add_items_to_playlist response_dict:", response_dict=response_dict)
        return response_dict

    async def update_link_original_playlist(
        self,
        playlist_id: str = None,
        song_title_list: list[str] = None,
    ) -> bool:
        spotify_tracks_id = []
        for yt_video_title in song_title_list:
            spotify_track = await self.search_for_track(yt_video_title)
            if spotify_track:
                spotify_tracks_id.append(spotify_track.get("id"))
        item_track_id_list = await self.get_playlist_items_track_id(playlist_id=playlist_id)

        await self.remove_playlist_items(
            playlist_id=playlist_id,
            item_track_id_list=item_track_id_list,
        )

        await self.add_items_to_playlist(
            playlist_id=playlist_id,
            track_id_list=spotify_tracks_id,
        )
        return True
