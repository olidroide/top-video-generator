import random
from contextlib import asynccontextmanager
from datetime import datetime
from typing import TypeVar

import aiohttp
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.discovery_cache.base import Cache
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from pydantic import BaseModel

from src.db_client import DatabaseClient
from src.logger import get_logger
from src.settings import get_app_settings

logger = get_logger(__name__)


@asynccontextmanager
async def get_default_client():
    conn = None
    async with aiohttp.ClientSession(
        connector=conn,
        headers={"Accept": "application/json"},
        timeout=aiohttp.ClientTimeout(total=30),
    ) as client:
        yield client


class MemoryCache(Cache):
    _CACHE = {}

    def get(self, url):
        return MemoryCache._CACHE.get(url)

    def set(self, url, content):
        MemoryCache._CACHE[url] = content


class YTClient:
    YT_API_SERVICE_NAME = "youtube"
    YT_API_VERSION = "v3"

    def __init__(self) -> None:
        super().__init__()
        self._yt_client_secret_file_name: str = get_app_settings().yt_client_secret_file
        self._yt_redirect_uri: str = get_app_settings().yt_redirect_uri
        self._yt_search_region_code: str = get_app_settings().yt_search_region_code
        self._yt_search_language_code: str = get_app_settings().yt_search_language_code
        self._yt_search_category_code: str = get_app_settings().yt_search_category_code
        self._yt_auth_user_id: str = get_app_settings().yt_auth_user_id
        self._yt_tags: list[str] = get_app_settings().yt_tags.split(",")
        self._memory_cache = MemoryCache()
        self._authenticated_service = None

    def get_authenticated_service(self):
        yt_auth = DatabaseClient().get_yt_auth(self._yt_auth_user_id)
        credentials = Credentials(**yt_auth.dict())
        if not self._authenticated_service:
            self._authenticated_service = build(
                serviceName=self.YT_API_SERVICE_NAME,
                version=self.YT_API_VERSION,
                credentials=credentials,
                cache=self._memory_cache,
                # cache_discovery=False,
            )
        return self._authenticated_service

    def _get_flow(self) -> Flow:
        flow = Flow.from_client_secrets_file(
            self._yt_client_secret_file_name,
            scopes=[
                "https://www.googleapis.com/auth/youtube.upload",
                "https://www.googleapis.com/auth/youtube",
                "https://www.googleapis.com/auth/youtube.force-ssl",
                "https://www.googleapis.com/auth/youtube.readonly",
            ],
        )
        flow.redirect_uri = self._yt_redirect_uri
        return flow

    async def step_1_get_authentication_url(self):
        flow = self._get_flow()
        authorization_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
        )
        return authorization_url

    def step_2_exchange_code_authentication(self, url_requested: str) -> dict:
        flow = self._get_flow()
        flow.fetch_token(authorization_response=url_requested)
        credentials: Credentials = flow.credentials

        return {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes,
        }

    async def _fetch_popular_videos(self, max_results: int = 25) -> dict:
        try:
            youtube = self.get_authenticated_service()
            response = (
                youtube.videos()
                .list(
                    part="contentDetails",
                    chart="mostPopular",
                    hl=self._yt_search_language_code,
                    maxResults=max_results,
                    regionCode=self._yt_search_region_code,
                    videoCategoryId=self._yt_search_category_code,
                )
                .execute()
            )

        except HttpError as e:
            logger.error("An error occurred", error=e)
            response = {}

        return response

    async def _get_uploads_playlist(self) -> str | None:
        playlist_id = None
        try:
            youtube = self.get_authenticated_service()
            response = youtube.channels().list(part="contentDetails", mine=True).execute()
            playlist_id = (
                response.get("items", []).pop().get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
            )
        except HttpError as e:
            logger.error("An error occurred", error=e)

        return playlist_id

    async def _fetch_videos_of_playlist(self, playlist_id: str, max_results: int = 25) -> dict:
        try:
            youtube = self.get_authenticated_service()
            response = (
                youtube.playlistItems()
                .list(
                    part="contentDetails",
                    playlistId=playlist_id,
                    maxResults=max_results,
                )
                .execute()
            )

        except HttpError as e:
            logger.error("An error occurred", error=e)
            response = {}

        return response

    async def _fetch_video_details(self, video_id: str) -> dict:
        try:
            youtube = self.get_authenticated_service()
            response = (
                youtube.videos()
                .list(
                    part="snippet,contentDetails,statistics",
                    id=video_id,
                )
                .execute()
            )

        except HttpError as e:
            logger.error("An error occurred", error=e)
            response = {}

        return response

    async def _fetch_playlist_items(self, playlist_id: str) -> dict:
        try:
            youtube = self.get_authenticated_service()
            response = (
                youtube.playlistItems()
                .list(
                    part="snippet",
                    playlistId=playlist_id,
                    maxResults=50,
                )
                .execute()
            )

        except HttpError as e:
            logger.error("An error occurred", error=e)
            response = {}

        return response

    async def _delete_playlist_item(
        self,
        playlist_item_id: str,
    ) -> dict:
        try:
            youtube = self.get_authenticated_service()
            response = youtube.playlistItems().delete(id=playlist_item_id).execute()
        except HttpError as e:
            logger.error("An error occurred", error=e)
            response = {}

        return response

    async def _add_playlist_item(
        self,
        playlist_id: str,
        video_id: str,
        position: int,
    ) -> dict:
        try:
            youtube = self.get_authenticated_service()
            response = (
                youtube.playlistItems()
                .insert(
                    part="snippet",
                    body={
                        "snippet": {
                            "playlistId": playlist_id,
                            "resourceId": {
                                "kind": "youtube#video",
                                "videoId": video_id,
                            },
                            "position": position,
                        }
                    },
                )
                .execute()
            )

        except HttpError as e:
            logger.error("An error occurred", error=e)
            response = {}

        return response

    async def get_popular_videos(
        self,
        max_results: int = 25,
    ):
        data = YTRoot.parse_obj(await self._fetch_popular_videos(max_results=max_results))
        return data

    async def get_videos_published(self):
        playlist_id = await self._get_uploads_playlist()
        data = YTRoot.parse_obj(await self._fetch_videos_of_playlist(playlist_id=playlist_id))
        return data

    async def get_video_details(self, video_id: str):
        data = YTRoot.parse_obj(await self._fetch_video_details(video_id=video_id))
        return data

    async def get_playlist_details(self, playlist_id: str):
        data = YTRoot.parse_obj(await self._fetch_playlist_items(playlist_id=playlist_id))
        return data

    async def delete_playlist_item(self, playlist_item_id: str):
        await self._delete_playlist_item(playlist_item_id=playlist_item_id)

    async def add_playlist_item(
        self,
        playlist_id: str,
        video_id: str,
        position: int,
    ):
        data = YTVideo.parse_obj(
            await self._add_playlist_item(
                playlist_id=playlist_id,
                video_id=video_id,
                position=position,
            )
        )
        return data

    async def update_link_original_playlist(
        self,
        playlist_id: str = None,
        yt_video_id_list: list[str] = None,
    ) -> bool | None:
        if not playlist_id:
            logger.warning("cannot update link original playlist without playlist_id param")
            return

        if not yt_video_id_list:
            logger.warning("cannot update link original playlist without yt video id list param")
            return

        playlist_details = await self.get_playlist_details(playlist_id=playlist_id)
        for playlist_item in playlist_details.items:
            try:
                await self.delete_playlist_item(playlist_item_id=playlist_item.id)
            except HttpError as e:
                logger.error("fail to remove", playlist_item_id=playlist_item.id, error=e)

        for index, yt_video_id in enumerate(yt_video_id_list):
            try:
                await self.add_playlist_item(
                    playlist_id=playlist_id,
                    video_id=yt_video_id,
                    position=index,
                )
            except HttpError as e:
                logger.error(
                    "fail to add playlist item ",
                    playlist_id=playlist_id,
                    video_id=yt_video_id,
                    position=index,
                    error=e,
                )

        return True

    async def upload_video(
        self,
        video_path,
        title,
        description,
        thumbnail_path: str = None,
        playlist_id: str = None,
        tags: list[str] = None,
    ) -> str | None:
        yt_tags = [tag.replace("@@YEAR@@", str(datetime.utcnow().year)) for tag in self._yt_tags]
        yt_tags.extend([tag.replace("#", "") for tag in tags] if tags else [])
        max_tags = 30

        try:
            youtube = self.get_authenticated_service()
            media = MediaFileUpload(video_path, chunksize=-1, resumable=True)

            title_max_length = 95
            title_formatted = title[:title_max_length]

            description_max_length = 4900
            description_formatted = description[:description_max_length]

            video = (
                youtube.videos()
                .insert(
                    autoLevels=True,
                    notifySubscribers=True,
                    stabilize=False,
                    part="snippet,status",
                    # TODO future support multiple managed yt accounts?
                    # onBehalfOfContentOwner="",
                    # onBehalfOfContentOwnerChannel="",
                    body={
                        "snippet": {
                            "title": title_formatted,
                            "description": description_formatted,
                            "categoryId": self._yt_search_category_code,
                            "defaultAudioLanguage": self._yt_search_language_code,
                            "tags": yt_tags[:max_tags],
                        },
                        "status": {
                            # "privacyStatus": "private",
                            "privacyStatus": "public",
                        },
                    },
                    media_body=media,
                )
                .execute()
            )

            video_id = video["id"]
            logger.debug("Uploaded video:", video=video_id)

            if thumbnail_path:
                logger.debug("set thumbnail video", video=video_id, playlist_id=thumbnail_path)

                youtube.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(thumbnail_path)).execute()

            if playlist_id:
                logger.debug("insert video into playlist", video=video_id, playlist_id=playlist_id)

                youtube.playlistItems().insert(
                    part="snippet",
                    body={
                        "snippet": {
                            "playlistId": playlist_id,
                            "resourceId": {
                                "kind": "youtube#video",
                                "videoId": video_id,
                            },
                        }
                    },
                ).execute()

        except HttpError as e:
            logger.error("An error occurred", error=e)
            return None
        return video_id


class YTClientFake(YTClient):
    async def _get_uploads_playlist(self) -> str | None:
        return "U*****_____w"

    async def _fetch_videos_of_playlist(self, playlist_id: str, max_results: int = 25) -> dict:
        return {
            "kind": "youtube#playlistItemListResponse",
            "etag": "zoTYDdEofF4fSsktxSrXZrSu9OA",
            "nextPageToken": "EAAaBlBUOkNBTQ",
            "items": [
                {
                    "kind": "youtube#playlistItem",
                    "etag": "lSpcQC3nkRqT89JgCqXVHprgMfp",
                    "id": "VVVkdVF2UUQxZThkZkc0SWRfbVg5VTh3LmV3UWFKY2ZsMVFR",
                    "contentDetails": {
                        "videoId": "miQaJcfl1RR",
                        "videoPublishedAt": "2023-08-21T16:23:19Z",
                    },
                },
                {
                    "kind": "youtube#playlistItem",
                    "etag": "ixsz8c7RTifBOQpJLOfUUXo73Yp",
                    "id": "HGNkdVF2UUQxZThkZkc0SWRfbVg5VTh3LjVwVWlPN3ZYN9NZ",
                    "contentDetails": {
                        "videoId": "7pUiO2vN7CY",
                        "videoPublishedAt": "2023-08-21T12:24:58Z",
                    },
                },
                {
                    "kind": "youtube#playlistItem",
                    "etag": "YYVewPeIn5MjF37bGh4-q_vxuyU",
                    "id": "VVVkdVF2UUQxZThkZkc0SWRfbVg5VTh3LkdwSktpU2tLX25N",
                    "contentDetails": {
                        "videoId": "NpSKlSkK_nM",
                        "videoPublishedAt": "2023-08-20T16:27:21Z",
                    },
                },
            ],
            "pageInfo": {
                "totalResults": 66,
                "resultsPerPage": 3,
            },
        }

    async def _fetch_popular_videos(self, max_results: int = 25) -> dict:
        return {
            "kind": "youtube#videoListResponse",
            "etag": "Wzlg80cIbrCY5QULz2PWF2BEBew",
            "items": [
                {
                    "kind": "youtube#video",
                    "etag": "cPAdfxNhdOVo1za3s-bHaS0VKUU",
                    "id": "cAMHx-m9oh8",
                    "contentDetails": {
                        "duration": "PT4M1S",
                        "dimension": "2d",
                        "definition": "hd",
                        "caption": "true",
                        "licensedContent": True,
                        "contentRating": {},
                        "projection": "rectangular",
                    },
                },
                {
                    "kind": "youtube#video",
                    "etag": "d1-XMo82DJUpgRuDykOpkEAfV5c",
                    "id": "pg2tsJErYH4",
                    "contentDetails": {
                        "duration": "PT2M30S",
                        "dimension": "2d",
                        "definition": "hd",
                        "caption": "false",
                        "licensedContent": True,
                        "contentRating": {},
                        "projection": "rectangular",
                    },
                },
                {
                    "kind": "youtube#video",
                    "etag": "N9dbWNTnIIxAY9Bdq1hQKrXkaas",
                    "id": "jWgm_wlGJqQ",
                    "contentDetails": {
                        "duration": "PT4M54S",
                        "dimension": "2d",
                        "definition": "hd",
                        "caption": "false",
                        "licensedContent": True,
                        "contentRating": {},
                        "projection": "rectangular",
                    },
                },
                {
                    "kind": "youtube#video",
                    "etag": "9RYlT4HM5bUJGZSCr87XCfcZDOw",
                    "id": "0n7AWxYCj9I",
                    "contentDetails": {
                        "duration": "PT4M14S",
                        "dimension": "2d",
                        "definition": "hd",
                        "caption": "true",
                        "licensedContent": True,
                        "contentRating": {},
                        "projection": "rectangular",
                    },
                },
                {
                    "kind": "youtube#video",
                    "etag": "i0kTJZuK0if5_6HrTQhN0_C7Ilc",
                    "id": "ND9obil2gu8",
                    "contentDetails": {
                        "duration": "PT3M6S",
                        "dimension": "2d",
                        "definition": "hd",
                        "caption": "false",
                        "licensedContent": True,
                        "contentRating": {},
                        "projection": "rectangular",
                    },
                },
                {
                    "kind": "youtube#video",
                    "etag": "7YB7O_sQmEe-IrFeFALREfZ0hdM",
                    "id": "8sLS2knUa6Y",
                    "contentDetails": {
                        "duration": "PT3M36S",
                        "dimension": "2d",
                        "definition": "hd",
                        "caption": "false",
                        "licensedContent": True,
                        "contentRating": {},
                        "projection": "rectangular",
                    },
                },
                {
                    "kind": "youtube#video",
                    "etag": "tIQi6f6hUmLhchv6_pIpodvyrDc",
                    "id": "SnXjGLFGCQU",
                    "contentDetails": {
                        "duration": "PT3M54S",
                        "dimension": "2d",
                        "definition": "hd",
                        "caption": "false",
                        "licensedContent": True,
                        "contentRating": {},
                        "projection": "rectangular",
                    },
                },
                {
                    "kind": "youtube#video",
                    "etag": "s2jYM3b2lyGy4ZHW1aXqndnwZ1o",
                    "id": "WwyE7P8jPpE",
                    "contentDetails": {
                        "duration": "PT3M15S",
                        "dimension": "2d",
                        "definition": "hd",
                        "caption": "false",
                        "licensedContent": True,
                        "contentRating": {},
                        "projection": "rectangular",
                    },
                },
                {
                    "kind": "youtube#video",
                    "etag": "dQ9TIrRxzGqR_EMKBtZ8PIjtwOM",
                    "id": "Gym3vzboXlY",
                    "contentDetails": {
                        "duration": "PT3M40S",
                        "dimension": "2d",
                        "definition": "hd",
                        "caption": "false",
                        "licensedContent": True,
                        "contentRating": {},
                        "projection": "rectangular",
                    },
                },
                {
                    "kind": "youtube#video",
                    "etag": "fyXwbDazV1W6bFbau-7vFxR6CyM",
                    "id": "0SVWTNwhAtA",
                    "contentDetails": {
                        "duration": "PT3M14S",
                        "dimension": "2d",
                        "definition": "hd",
                        "caption": "true",
                        "licensedContent": True,
                        "contentRating": {},
                        "projection": "rectangular",
                    },
                },
                {
                    "kind": "youtube#video",
                    "etag": "TWegMeJoAQgtJv0MZeG44RCkEK4",
                    "id": "TUGfWIO_fFI",
                    "contentDetails": {
                        "duration": "PT4M",
                        "dimension": "2d",
                        "definition": "hd",
                        "caption": "false",
                        "licensedContent": True,
                        "contentRating": {},
                        "projection": "rectangular",
                    },
                },
                {
                    "kind": "youtube#video",
                    "etag": "1Rv5XUnmQRxKWobWKPlGB_YPoP0",
                    "id": "2iaE1ayfc1I",
                    "contentDetails": {
                        "duration": "PT3M6S",
                        "dimension": "2d",
                        "definition": "hd",
                        "caption": "false",
                        "licensedContent": True,
                        "contentRating": {},
                        "projection": "rectangular",
                    },
                },
                {
                    "kind": "youtube#video",
                    "etag": "QtZyZulsQFgIOd1oRfMJEnl5pHA",
                    "id": "uMcU5qVz9YE",
                    "contentDetails": {
                        "duration": "PT2M24S",
                        "dimension": "2d",
                        "definition": "hd",
                        "caption": "true",
                        "licensedContent": True,
                        "contentRating": {},
                        "projection": "rectangular",
                    },
                },
                {
                    "kind": "youtube#video",
                    "etag": "3wtWjWeqT5Q4P1PswC_rrHSCrHw",
                    "id": "Fmnn-PkppVc",
                    "contentDetails": {
                        "duration": "PT3M53S",
                        "dimension": "2d",
                        "definition": "hd",
                        "caption": "false",
                        "licensedContent": True,
                        "contentRating": {},
                        "projection": "rectangular",
                    },
                },
                {
                    "kind": "youtube#video",
                    "etag": "dvSDnTUF47yvLE46pGlx6TsAP6g",
                    "id": "4rFVRTSxwRQ",
                    "contentDetails": {
                        "duration": "PT5M28S",
                        "dimension": "2d",
                        "definition": "hd",
                        "caption": "false",
                        "licensedContent": True,
                        "contentRating": {},
                        "projection": "rectangular",
                    },
                },
                {
                    "kind": "youtube#video",
                    "etag": "PB9LY-L1opvgRs2CMJ28o9UvEk4",
                    "id": "T9QmIhnk874",
                    "contentDetails": {
                        "duration": "PT3M58S",
                        "dimension": "2d",
                        "definition": "hd",
                        "caption": "false",
                        "licensedContent": True,
                        "contentRating": {},
                        "projection": "rectangular",
                    },
                },
                {
                    "kind": "youtube#video",
                    "etag": "HkqAzE6UvFGAYBD1wohVRdZPpGA",
                    "id": "XeGdY8RoxQY",
                    "contentDetails": {
                        "duration": "PT3M31S",
                        "dimension": "2d",
                        "definition": "hd",
                        "caption": "false",
                        "licensedContent": True,
                        "contentRating": {},
                        "projection": "rectangular",
                    },
                },
                {
                    "kind": "youtube#video",
                    "etag": "tktkQuxUgJJHHor3SeqzzTf2lWM",
                    "id": "q1PLUj85fHg",
                    "contentDetails": {
                        "duration": "PT4M57S",
                        "dimension": "2d",
                        "definition": "hd",
                        "caption": "false",
                        "licensedContent": True,
                        "contentRating": {},
                        "projection": "rectangular",
                    },
                },
                {
                    "kind": "youtube#video",
                    "etag": "2DVzGHuNNfgxEFh_n73id8Pk7gg",
                    "id": "8l32-NbQW1E",
                    "contentDetails": {
                        "duration": "PT3M4S",
                        "dimension": "2d",
                        "definition": "hd",
                        "caption": "true",
                        "licensedContent": True,
                        "contentRating": {},
                        "projection": "rectangular",
                    },
                },
                {
                    "kind": "youtube#video",
                    "etag": "1uHoUZMgdvkqBCMLSy5B6lP9Kf8",
                    "id": "3VSZE4t9H3M",
                    "contentDetails": {
                        "duration": "PT1M4S",
                        "dimension": "2d",
                        "definition": "hd",
                        "caption": "true",
                        "licensedContent": True,
                        "contentRating": {},
                        "projection": "rectangular",
                    },
                },
                {
                    "kind": "youtube#video",
                    "etag": "ESfKqZi9Crl52nCnOauddZwqAf8",
                    "id": "7rzSX22QRUI",
                    "contentDetails": {
                        "duration": "PT10M15S",
                        "dimension": "2d",
                        "definition": "hd",
                        "caption": "true",
                        "licensedContent": True,
                        "contentRating": {},
                        "projection": "rectangular",
                    },
                },
                {
                    "kind": "youtube#video",
                    "etag": "I25sui2BjN72gybyI0oNZuxInWM",
                    "id": "TeB3Vw7rEMU",
                    "contentDetails": {
                        "duration": "PT5M15S",
                        "dimension": "2d",
                        "definition": "hd",
                        "caption": "false",
                        "licensedContent": True,
                        "contentRating": {},
                        "projection": "rectangular",
                    },
                },
                {
                    "kind": "youtube#video",
                    "etag": "LCfp4pt-NkzCAQIwQdLwZbRukIM",
                    "id": "LA4ROL4ZxdI",
                    "contentDetails": {
                        "duration": "PT3M",
                        "dimension": "2d",
                        "definition": "hd",
                        "caption": "false",
                        "licensedContent": True,
                        "contentRating": {},
                        "projection": "rectangular",
                    },
                },
                {
                    "kind": "youtube#video",
                    "etag": "47QqUwfLKYbzFQtLq18v_6E_4Kc",
                    "id": "6vEAJjiiNVI",
                    "contentDetails": {
                        "duration": "PT4M12S",
                        "dimension": "2d",
                        "definition": "hd",
                        "caption": "false",
                        "licensedContent": True,
                        "contentRating": {},
                        "projection": "rectangular",
                    },
                },
                {
                    "kind": "youtube#video",
                    "etag": "_DcOFTpxKcBYhe0IlxfgLq1vTX0",
                    "id": "MAa_8XwAVlA",
                    "contentDetails": {
                        "duration": "PT5M14S",
                        "dimension": "2d",
                        "definition": "hd",
                        "caption": "false",
                        "licensedContent": True,
                        "contentRating": {},
                        "projection": "rectangular",
                    },
                },
            ],
            "nextPageToken": "CBkQAA",
            "pageInfo": {"totalResults": 30, "resultsPerPage": 25},
        }

    async def _fetch_video_details(self, video_id: str) -> dict:
        return {
            "kind": "youtube#videoListResponse",
            "etag": "s0hyMDH1MOAJZVFaNbNDToI8MDw",
            "items": [
                {
                    "kind": "youtube#video",
                    "etag": "WJaiWdgs9xNNoJgB_rkc49w_4Vs",
                    "id": video_id,
                    "snippet": {
                        "publishedAt": "2023-05-15T12:30:06Z",
                        "channelId": "UC783dnzJqf2ghHp_pFLYbGA",
                        "title": "Kya Loge Tum | Akshay Kumar | Amyra Dastur | BPraak | Jaani | Arvindr Khaira | Zohrajabeen",
                        "description": "Desi Melodies presents in association with Cape Of Good Films & Azeem Dayani the first single, 'Kya Loge Tum,' from B Praak's highly anticipated debut album, \"Zohrajabeen.\" The star-studded team of B Praak, Jaani, Arvindr Khaira, and Akshay Kumar reunites for the first time since the pop-culture-defining songs 'Filhall' and 'Filhaal 2.'\n\nThe emotionally charged lyrics written by Jaani, along with his heart-wrenching composition, add an extra layer of depth to the already powerful track produced by B Praak himself. Arvindr Khaira takes it to the next level with his visionary direction, featuring Akshay Kumar and Amyra Dastur's palpable chemistry that will leave you wanting more.\n\nListen to 'Kya Loge Tum' - https://bit.ly/KyaLogeTum\n\nSinger and Music - B Praak\nFeaturing - Akshay Kumar and Amyra Dastur\nSupporting Cast- Karamm S Rajpal\nLyricist and Composer - Jaani\nDirector - Arvindr Khaira \n\nMusic Arrangements - Gaurav Dev and Kartik Dev \nVeena Player - Rajhesh Vaidhya\nMix And Mastered - Gurjinder Guri and Akaash Bambar (Saffron Touch)\nAdditional Programming - Aditya Pushkarna \n\nChoreographer - Rajit Dev\nEditor - Adele Pereira\nColorist - Onkar Singh\nVFX - Gagan Matharoo\nVideo Supervisor/Creative Director - Amanninder Singh\nChief AD - Sukhman Sukhu\n1st AD - Satnam Singh\nAssistant Director - Ashish Dahda, Jass Sivia, and Faizal\nArt Supervisor -  Faisal Saifi  \nTalent Head - Gaaurav Sharma\nCostumes - Outdo\nProduction House - Metro Talkies \nLine Producer - Anuj Tiwari & Vikrant Kaushik \nArt Director - Raj Shah\nDOP - Alpesh Nagar \nAC - Janil Mehta \nFocus Puller 1 - Akrarm\nFocus Puller 2 - Chandra Babu\nGaffar - Faruk Mondal \nMakeup - Karan Singh \nProduction Controller - Umesh Kamble\nProduction Manager - Indra Sharma and Dharmesh Waghela \n2nd AD - Rohan Pawar, Mahi Rathore, Manan Parihar, \nDIT - Vishal Chavan\nCasting of Karamm Rajpal - Rahul Gaur\nBehind The Scenes - Jogi Singh Munde\nPoster Design - Aman Kalsi\n\nTeam Akshay Kumar\nBusiness Head - Vedant Baali \nPA - Zenobia Kohla \nDigital Manager - Shilpa Lakhani\nHair Stylist - Shivcharan Geloth \nSpot - Sukhwinder Singh\nMakeup - Narendra Kushwah\nBodyguard - Shrishial Tele\nDriver - Youvraj Kamble\nPersonal Trainer - Kruttika Ranjane\n\nTeam Amyra Dastur\nMakeup- Mahima Motwani\nHair - Tabassum Sayed\nOutfit - Outdo (Lavika Singh)\nManager- Anusshi Arorah\n\nDigital Distribution - Universal Music \nProducer - Arvindr Khaira and Jaani\nFinance Team - Raghav Chugh\nProject by - Dilraj Nandha\nBrand Integration - Net Media (Sonal Talwar)\nDigital Promotions - Net Media \nLabel Relations and Marketing Manager - Sidhantha Jain \n\nLabel - Desi Melodies \nhttps://www.instagram.com/desimelodies/\n\n#AkshayKumar #Jaani #BPraak",
                        "thumbnails": {
                            "default": {
                                "url": "https://i.ytimg.com/vi/cAMHx-m9oh8/default.jpg",
                                "width": 120,
                                "height": 90,
                            },
                            "medium": {
                                "url": "https://i.ytimg.com/vi/cAMHx-m9oh8/mqdefault.jpg",
                                "width": 320,
                                "height": 180,
                            },
                            "high": {
                                "url": "https://i.ytimg.com/vi/cAMHx-m9oh8/hqdefault.jpg",
                                "width": 480,
                                "height": 360,
                            },
                            "standard": {
                                "url": "https://i.ytimg.com/vi/cAMHx-m9oh8/sddefault.jpg",
                                "width": 640,
                                "height": 480,
                            },
                            "maxres": {
                                "url": "https://i.ytimg.com/vi/cAMHx-m9oh8/maxresdefault.jpg",
                                "width": 1280,
                                "height": 720,
                            },
                        },
                        "channelTitle": "DM - Desi Melodies",
                        "tags": [
                            "filhall 2",
                            "Filhaal",
                            "akshay kumar",
                            "Bpraak",
                            "jaani",
                            "b praak new song",
                            "akshay kumar filhaal",
                            "arvindr khaira",
                            "latest hindi songs",
                            "latest punjabi songs",
                            "new romantic songs",
                            "latest sad song",
                            "Akshay kumar song",
                            "Jaani new song",
                            "new songs 2023",
                            "kya loge tum",
                            "akshay kumar song",
                            "love songs 2023",
                            "bpraak album",
                            "bpraak song",
                            "new songs sad",
                            "love songs",
                            "romantic hits",
                            "2023 songs",
                            "jaani 2023",
                            "akshay 2023",
                            "KYA LOGE TUM",
                            "Daulat yaan shohrat",
                            "lawaris hai pyar tera",
                            "zohrajabeen",
                            "Filhaal 3",
                        ],
                        "categoryId": "10",
                        "liveBroadcastContent": "none",
                        "localized": {
                            "title": "Kya Loge Tum | Akshay Kumar | Amyra Dastur | BPraak | Jaani | Arvindr Khaira | Zohrajabeen",
                            "description": "Desi Melodies presents in association with Cape Of Good Films & Azeem Dayani the first single, 'Kya Loge Tum,' from B Praak's highly anticipated debut album, \"Zohrajabeen.\" The star-studded team of B Praak, Jaani, Arvindr Khaira, and Akshay Kumar reunites for the first time since the pop-culture-defining songs 'Filhall' and 'Filhaal 2.'\n\nThe emotionally charged lyrics written by Jaani, along with his heart-wrenching composition, add an extra layer of depth to the already powerful track produced by B Praak himself. Arvindr Khaira takes it to the next level with his visionary direction, featuring Akshay Kumar and Amyra Dastur's palpable chemistry that will leave you wanting more.\n\nListen to 'Kya Loge Tum' - https://bit.ly/KyaLogeTum\n\nSinger and Music - B Praak\nFeaturing - Akshay Kumar and Amyra Dastur\nSupporting Cast- Karamm S Rajpal\nLyricist and Composer - Jaani\nDirector - Arvindr Khaira \n\nMusic Arrangements - Gaurav Dev and Kartik Dev \nVeena Player - Rajhesh Vaidhya\nMix And Mastered - Gurjinder Guri and Akaash Bambar (Saffron Touch)\nAdditional Programming - Aditya Pushkarna \n\nChoreographer - Rajit Dev\nEditor - Adele Pereira\nColorist - Onkar Singh\nVFX - Gagan Matharoo\nVideo Supervisor/Creative Director - Amanninder Singh\nChief AD - Sukhman Sukhu\n1st AD - Satnam Singh\nAssistant Director - Ashish Dahda, Jass Sivia, and Faizal\nArt Supervisor -  Faisal Saifi  \nTalent Head - Gaaurav Sharma\nCostumes - Outdo\nProduction House - Metro Talkies \nLine Producer - Anuj Tiwari & Vikrant Kaushik \nArt Director - Raj Shah\nDOP - Alpesh Nagar \nAC - Janil Mehta \nFocus Puller 1 - Akrarm\nFocus Puller 2 - Chandra Babu\nGaffar - Faruk Mondal \nMakeup - Karan Singh \nProduction Controller - Umesh Kamble\nProduction Manager - Indra Sharma and Dharmesh Waghela \n2nd AD - Rohan Pawar, Mahi Rathore, Manan Parihar, \nDIT - Vishal Chavan\nCasting of Karamm Rajpal - Rahul Gaur\nBehind The Scenes - Jogi Singh Munde\nPoster Design - Aman Kalsi\n\nTeam Akshay Kumar\nBusiness Head - Vedant Baali \nPA - Zenobia Kohla \nDigital Manager - Shilpa Lakhani\nHair Stylist - Shivcharan Geloth \nSpot - Sukhwinder Singh\nMakeup - Narendra Kushwah\nBodyguard - Shrishial Tele\nDriver - Youvraj Kamble\nPersonal Trainer - Kruttika Ranjane\n\nTeam Amyra Dastur\nMakeup- Mahima Motwani\nHair - Tabassum Sayed\nOutfit - Outdo (Lavika Singh)\nManager- Anusshi Arorah\n\nDigital Distribution - Universal Music \nProducer - Arvindr Khaira and Jaani\nFinance Team - Raghav Chugh\nProject by - Dilraj Nandha\nBrand Integration - Net Media (Sonal Talwar)\nDigital Promotions - Net Media \nLabel Relations and Marketing Manager - Sidhantha Jain \n\nLabel - Desi Melodies \nhttps://www.instagram.com/desimelodies/\n\n#AkshayKumar #Jaani #BPraak",
                        },
                        "defaultAudioLanguage": "hi",
                    },
                    "contentDetails": {
                        "duration": "PT4M1S",
                        "dimension": "2d",
                        "definition": "hd",
                        "caption": "true",
                        "licensedContent": True,
                        "contentRating": {},
                        "projection": "rectangular",
                    },
                    "statistics": {
                        "viewCount": random.randint(0, 53029987),
                        "likeCount": "856498",
                        "favoriteCount": "0",
                        "commentCount": "191319",
                    },
                }
            ],
            "pageInfo": {"totalResults": 1, "resultsPerPage": 1},
        }

    async def _fetch_playlist_items(self, playlist_id: str) -> dict:
        return {
            "kind": "youtube#playlistItemListResponse",
            "etag": "NQfXmbGsngTrhVitGh2wj1EEH-M",
            "items": [
                {
                    "kind": "youtube#playlistItem",
                    "etag": "3bHdPctYgExIi9YmhiR3WeZ_Na0",
                    "id": "UExaQUkzTGM3T3lnczJ3WkZaUnduNFRTVkJ5NDZBRGhMUy41NkI0NEY2RDEwNTU3Q0M2",
                    "snippet": {
                        "publishedAt": "2023-08-30T09:25:36Z",
                        "channelId": "UCduQvQD1e8dfG4Id_mX9U8w",
                        "title": "Jawan: Not Ramaiya Vastavaiya | Shah Rukh Khan | Atlee | Anirudh | Nayanthara | Vishal D | Shilpa R",
                        "description": 'Get ready to groove like never before as "Not Ramaiya Vastavaiya", the latest dance track from the highly-anticipated Atlee directorial, Jawan, is out now. The film stars Shah Rukh Khan, Vijay Sethupathi, Nayanthara, and Deepika Padukone (in a special appearance) and is set to release in cinemas on September 7, 2023, in Hindi, Tamil, and Telugu!\n\n#NotRamaiyaVastavaiya out now!\n\n♪Full Song Available on♪ \nJioSaavn: https://bit.ly/3srnLI5\nSpotify: https://bit.ly/3ssmbG1\nHungama: https://bit.ly/3OW4upT\nApple Music: https://bit.ly/3OYPyau\nAmazon Prime Music: https://bit.ly/44vEozG\nWynk: https://bit.ly/3L0roLy\nResso: https://bit.ly/47UA7Zy\nYouTube Music: https://bit.ly/3OWNbov\n\nMusic Credits:\nLanguage - Hindi\nSong Title - Not Ramaiya Vastavaiya \nAlbum / Movie - Jawan\nComposed by Anirudh Ravichander\nLyrics - Kumaar\nVocals - Anirudh Ravichander, Vishal Dadlani & Shilpa Rao\nChoreographer - Vaibhavi Merchant \n\nComposed, Arranged & Programmed by Anirudh Ravichander\nKeyboard, Synth & Rhythm Programmed by Anirudh Ravichander\nWhistle - Satish Raghunathan\nTabla - MT Aditya\nAdditional Rhythm Programmed by Shashank Vijay\nAdditional Keyboard Programmed by Arish-Pradeep PJ\n\nMusic Advisor - Ananthakrrishnan\nCreative Consultant - Sajith Satya\nMusic Editor - Harish Ram L H\nRecorded at Albuquerque Records, Chennai. Engineered by Srinivasan M, Shivakiran S, Rajesh Kannan, Jishnu Vijayan\nYRF Studios, Mumbai, Engineered by Vijay Dayal & Chinmay\nMixed by Vinay Sridhar & Srinivasan M at Albuquerque Records, Chennai\nMastered by Luca Pretolesi at Studio DMI, Las Vegas Assisted by Alistair Pintus \nMusic Coordinator - Velavan B\n\nLyrics:\n\nDance with me now I can’t break away\nAaj sari fikreiin tu shake away\nShake away\nDil thirakta dance wale groove pe\nNachun mai to step mera vekh ve\n\nVekh ve\nAaj sare kaam kal pe talke\nTak dhina dhin nache jayein taal pe\nDisko jaz blues sare bhoolke\nDesi wale geet pe tu jhoolke\nPehle kiya chaiya chaiya re\nAb kar tha tha thaiyya\nRamiya vasta vaiya..!\nAntra\n\nSama mazedar hua houle houle\nThoda nashedar hua\nMan ye dole\nAaj koi nachta hua sa jadu\nSar pe swar hua\nDil ye bole\nDoobi khushiyon mein\nRaat apni jabse suraj dhala\nChodh sharmana aaj nachle pair chakkle zara\n\nPahle kiya chaiya chaiiya re\nAb kar tata thaiya\nRamiya vasta vaiyaa..!\n\n\n___________________________________\nEnjoy & stay connected with us!\n👉 Subscribe to T-Series: http://bit.ly/TSeriesYouTube\n👉 Like us on Facebook: https://www.facebook.com/tseriesmusic\n👉 Follow us on X: https://twitter.com/tseries\n👉 Follow us on Instagram: http://bit.ly/InstagramTseries',
                        "thumbnails": {
                            "default": {
                                "url": "https://i.ytimg.com/vi/ohS06vkHjLE/default.jpg",
                                "width": 120,
                                "height": 90,
                            },
                            "medium": {
                                "url": "https://i.ytimg.com/vi/ohS06vkHjLE/mqdefault.jpg",
                                "width": 320,
                                "height": 180,
                            },
                            "high": {
                                "url": "https://i.ytimg.com/vi/ohS06vkHjLE/hqdefault.jpg",
                                "width": 480,
                                "height": 360,
                            },
                            "standard": {
                                "url": "https://i.ytimg.com/vi/ohS06vkHjLE/sddefault.jpg",
                                "width": 640,
                                "height": 480,
                            },
                            "maxres": {
                                "url": "https://i.ytimg.com/vi/ohS06vkHjLE/maxresdefault.jpg",
                                "width": 1280,
                                "height": 720,
                            },
                        },
                        "channelTitle": "Sat Deva Singh",
                        "playlistId": "PLZAI3Lc7Oygs2wZFZRwn4TSVBy46ADhLS",
                        "position": 0,
                        "resourceId": {"kind": "youtube#video", "videoId": "ohS06vkHjLE"},
                        "videoOwnerChannelTitle": "T-Series",
                        "videoOwnerChannelId": "UCq-Fj5jknLsUf-MWSy4_brA",
                    },
                },
                {
                    "kind": "youtube#playlistItem",
                    "etag": "JbdvcmUtA5wFaCUfvMzVS3z34hQ",
                    "id": "UExaQUkzTGM3T3lnczJ3WkZaUnduNFRTVkJ5NDZBRGhMUy4yODlGNEE0NkRGMEEzMEQy",
                    "snippet": {
                        "publishedAt": "2023-08-30T09:34:23Z",
                        "channelId": "UCduQvQD1e8dfG4Id_mX9U8w",
                        "title": "Udd Jaa Kaale Kaava | Gadar 2 | Sunny Deol, Ameesha | Mithoon, Udit N, Alka Y | Uttam S,Anand Bakshi",
                        "description": "👉🏻 SUBSCRIBE to Zee Music Company - https://bit.ly/2yPcBkS\n\nTo Stream & Download Full Song: \nJioSaavn - https://bit.ly/3NTdexz\nResso - https://bit.ly/3JySKrl\nGaana - https://bit.ly/3XCTfqj\niTunes - https://apple.co/46pbpjp\nApple Music - https://apple.co/46pbpjp\nAmazon Prime Music - https://amzn.to/44k6cre\nWynk Music - https://wynk.in/u/G4zKQyQiw\nHungama - https://bit.ly/4417fMR\nYouTube Music - https://bit.ly/3XyW6ke\n\nSong: Udd Jaa Kaale Kaava\nSingers: Udit Narayan & Alka Yagnik\nSong Recreated and Rearranged by: Mithoon\nOriginal Composition: Uttam Singh\nLyrics: Anand Bakshi\nCreative Head: Anugrah\nMusic Production: Godswill Mergulhao & Kaushal Gohil\nMusic Assts: Anugrah, Godswill Mergulhao, Eli Rodrigues & Kaushal Gohil\nWorld Strokes: Tapas Roy\nSarangi: Dilshad Khan\nBass Guitar: Lemuel Mergulhao\nChorus: Shahzad Ali, Sudhir Yaduvanshi & Sahil Kumar\nSong Recorded at Living Water Music by: Eli Rodrigues\nSong Mixed & Mastered by: Eric Pillai at Future Sound Of Bombay\nMixing Asst: Michael Edwin Pillai\nProject Co-ordinated by: Kaushal Gohil\nManager to Mithoon: Vijay Iyer\nLegal Advisor to Mithoon: Shyam Dewani\n\n#Gadar2 in cinemas 11th August\n\nZee Studios Presents\nDirected by: Anil Sharma\nProduced by: Zee Studios\nProduced by: Anil Sharma Productions & Kamal Mukut\nCo-Producer: Suman Sharma\nWritten by: Shaktimaan Talwar\nDOP: Najeeb Khan\nChoreographer: Shabina Khan\n \nStarring: Sunny Deol, Ameesha Patel, Utkarsh Sharma, Manish Wadhwa, Gaurav Chopra & Luv Sinha\nIntroducing - Simratt Kaur Randhawa\n\n\nMusic on Zee Music Company\n\nConnect with us on :\nTwitter - https://www.twitter.com/ZeeMusicCompany\nFacebook - https://www.facebook.com/zeemusiccompany\nInstagram - https://www.instagram.com/zeemusiccompany\nYouTube - http://bit.ly/TYZMC",
                        "thumbnails": {
                            "default": {
                                "url": "https://i.ytimg.com/vi/7VppHj0Rue0/default.jpg",
                                "width": 120,
                                "height": 90,
                            },
                            "medium": {
                                "url": "https://i.ytimg.com/vi/7VppHj0Rue0/mqdefault.jpg",
                                "width": 320,
                                "height": 180,
                            },
                            "high": {
                                "url": "https://i.ytimg.com/vi/7VppHj0Rue0/hqdefault.jpg",
                                "width": 480,
                                "height": 360,
                            },
                            "standard": {
                                "url": "https://i.ytimg.com/vi/7VppHj0Rue0/sddefault.jpg",
                                "width": 640,
                                "height": 480,
                            },
                            "maxres": {
                                "url": "https://i.ytimg.com/vi/7VppHj0Rue0/maxresdefault.jpg",
                                "width": 1280,
                                "height": 720,
                            },
                        },
                        "channelTitle": "Sat Deva Singh",
                        "playlistId": "PLZAI3Lc7Oygs2wZFZRwn4TSVBy46ADhLS",
                        "position": 1,
                        "resourceId": {"kind": "youtube#video", "videoId": "7VppHj0Rue0"},
                        "videoOwnerChannelTitle": "Zee Music Company",
                        "videoOwnerChannelId": "UCFFbwnve3yF62-tVXkTyHqg",
                    },
                },
            ],
            "pageInfo": {"totalResults": 2, "resultsPerPage": 5},
        }

    async def upload_video(
        self,
        video_path,
        title,
        description,
        thumbnail_path: str = None,
        playlist_id: str = None,
        tags: list[str] = None,
    ):
        return True


YTClientT = TypeVar("YTClientT", bound=YTClient)


def get_yt_client() -> YTClientT:
    settings = get_app_settings()
    return YTClient() if settings.is_production_env else YTClientFake()


class YTPageInfo(BaseModel):
    totalResults: int
    resultsPerPage: int


class YTBase(BaseModel):
    kind: str
    etag: str
    nextPageToken: str | None
    pageInfo: YTPageInfo | None


class YTVideoContentDetails(BaseModel):
    duration: str | None
    dimension: str | None  # 2d
    definition: str | None  # hd
    caption: str | None
    licensedContent: bool | None
    contentRating: dict | None
    projection: str | None  # rectangular
    videoId: str | None
    videoPublishedAt: datetime | None


class YTThumbnail(BaseModel):
    url: str
    width: int
    height: int


class YTVideoSnippetThumbnail(BaseModel):
    default: YTThumbnail | None
    medium: YTThumbnail | None
    high: YTThumbnail | None
    standard: YTThumbnail | None
    maxres: YTThumbnail | None


class YTVideoSnippetLocalized(BaseModel):
    title: str | None
    description: str | None


class YTVideoSnippetResource(BaseModel):
    videoId: str


class YTVideoSnippet(BaseModel):
    publishedAt: datetime | None
    channelId: str | None
    title: str | None
    description: str | None
    thumbnails: YTVideoSnippetThumbnail | None
    channelTitle: str | None
    tags: list[str] | None
    categoryId: str | None
    liveBroadcastContent: str | None
    localized: YTVideoSnippetLocalized | None
    defaultAudioLanguage: str | None
    position: int | None
    playlistId: str | None
    videoOwnerChannelTitle: str | None
    videoOwnerChannelId: str | None
    resourceId: YTVideoSnippetResource | None


class YTVideContentStatistics(BaseModel):
    viewCount: int | None
    likeCount: int | None
    favoriteCount: int | None
    commentCount: int | None


class YTVideoStatus(BaseModel):
    embeddable: bool | None
    license: str | None  # "youtube
    privacyStatus: str | None  # "unlisted", "public", "private"
    publicStatsViewable: bool | None
    # publishAt
    selfDeclaredMadeForKids: bool | None
    madeForKids: bool | None
    rejectionReason: str | None  #
    uploadStatus: str | None


class YTVideoAgeGating(BaseModel):
    alcoholContent: bool | None
    restricted: bool | None
    videoGameRating: str | None


class YTVideoMonetizationDetailsAccess(BaseModel):
    allowed: bool | None


class YTVideoMonetizationDetails(BaseModel):
    access: YTVideoMonetizationDetailsAccess | None


class YTVideoTopicDetails(BaseModel):
    relevantTopicIds: list[str] | None
    topicCategories: list[str] | None
    topicIds: list[str] | None


class YTVideo(YTBase):
    id: str
    contentDetails: YTVideoContentDetails | None
    snippet: YTVideoSnippet | None
    statistics: YTVideContentStatistics | None
    status: YTVideoStatus | None
    ageGating: YTVideoAgeGating | None
    monetizationDetails: YTVideoMonetizationDetails | None
    topicDetails: YTVideoTopicDetails | None


class YTVideoUploadRequest(YTVideo):
    id: str | None


class YTRoot(YTBase):
    items: list[YTVideo]
