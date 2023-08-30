import json
import math
import pathlib
import random
import string
from contextlib import asynccontextmanager
from urllib.parse import urlencode

import aiohttp
from pydantic import BaseModel

from src.db_client import DatabaseClient, TikTokAuth
from src.logger import get_logger
from src.settings import get_app_settings

logger = get_logger(__name__)


class TiktokResponseData(BaseModel):
    pass


class TiktokResponseDataPublishVideoInitUrl(TiktokResponseData):
    publish_id: str | None
    upload_url: str | None


class TiktokResponseDataPublishQueryCreatorInfo(TiktokResponseData):
    creator_avatar_url: str | None
    creator_username: str | None
    creator_nickname: str | None
    privacy_level_options: list[str] | None
    comment_disabled: bool | None
    duet_disabled: bool | None
    stitch_disabled: bool | None
    max_video_post_duration_sec: int | None


class TiktokResponseError(BaseModel):
    code: str | None
    message: str | None
    logid: str | None


class TiktokResponse(BaseModel):
    data: TiktokResponseData | None
    error: TiktokResponseError | None


class TiktokResponsePublishQueryCreatorInfo(TiktokResponse):
    data: TiktokResponseDataPublishQueryCreatorInfo | None


class TiktokResponsePublishVideoInitUrl(TiktokResponse):
    data: TiktokResponseDataPublishVideoInitUrl | None


@asynccontextmanager
async def get_default_client():
    conn = None
    async with aiohttp.ClientSession(
        connector=conn,
        timeout=aiohttp.ClientTimeout(total=30),
    ) as client:
        yield client


class TikTokClient:
    _base_url = "https://open.tiktokapis.com"

    def __init__(self) -> None:
        super().__init__()
        self._tiktok_client_key: str = get_app_settings().tiktok_client_key
        self._tiktok_client_secret: str = get_app_settings().tiktok_client_secret
        self._tiktok_redirect_uri: str = get_app_settings().tiktok_redirect_uri
        self._tiktok_app_id: str = get_app_settings().tiktok_app_id
        self._tiktok_user_openid: str = get_app_settings().tiktok_user_openid

    async def _get_user_refresh_token(self, user_openid: str):
        tiktok_auth = DatabaseClient().get_tiktok_auth(user_openid)
        return tiktok_auth.refresh_token

    async def _get_user_token_bearer_credentials(self, user_openid: str):
        tiktok_auth = DatabaseClient().get_tiktok_auth(user_openid)
        return tiktok_auth.token

    async def step_1_get_authentication_url(self) -> str:
        _seed = 36
        random_code = "".join(
            random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(_seed)
        )
        scope = "user.info.basic,video.publish,video.upload"

        authorize_url = "https://www.tiktok.com/v2/auth/authorize/"
        query_params = {
            "client_key": self._tiktok_client_key,
            "scope": scope,
            "redirect_uri": self._tiktok_redirect_uri,
            "state": random_code.lower()[16:],
            "response_type": "code",
        }

        request_code_url = authorize_url + "?" + urlencode(query_params)

        logger.debug("url", request_code_url=request_code_url)
        return request_code_url

    async def step_2_exchange_code_authentication(self, user_code: str):
        authorize_url = f"{self._base_url}/v2/oauth/token/"
        data = {
            "client_key": self._tiktok_client_key,
            "client_secret": self._tiktok_client_secret,
            "code": user_code,
            "grant_type": "authorization_code",
            "redirect_uri": self._tiktok_redirect_uri,
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Cache-Control": "no-cache",
        }

        async with get_default_client() as client:
            response = await client.post(url=authorize_url, headers=headers, data=data)
            response_dict = await response.json()

        logger.debug("auth token:", response_dict=response_dict)
        return response_dict

    async def fetch_user_info(self):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {await self._get_user_token_bearer_credentials(self._tiktok_user_openid)}",
        }
        params = {
            "fields": "open_id,union_id,avatar_url,avatar_url_100,avatar_large_url,display_name",
        }
        url = "https://open.tiktokapis.com/v2/user/info/"
        async with get_default_client() as client:
            response = await client.get(url=url, headers=headers, params=params)
            response_dict = await response.json()
        logger.debug("response_dict:", response_dict=response_dict)

    async def refresh_token(self) -> str:
        url = f"{self._base_url}/v2/oauth/token/"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Cache-Control": "no-cache",
        }

        data = {
            "client_key": self._tiktok_client_key,
            "client_secret": self._tiktok_client_secret,
            "refresh_token": await self._get_user_refresh_token(self._tiktok_user_openid),
            "grant_type": "refresh_token",
        }

        async with get_default_client() as client:
            response = await client.post(url=url, headers=headers, data=data)
            response_dict = await response.json()

        logger.debug("response_dict:", response_dict=response_dict)
        tiktok_auth = DatabaseClient().add_or_update_tiktok_auth(
            tiktok_auth=TikTokAuth(
                token=response_dict.get("access_token"),
                refresh_token=response_dict.get("refresh_token"),
                client_id=response_dict.get("open_id"),
                scopes=response_dict.get("scope", "").split(","),
            )
        )
        return tiktok_auth.token

    async def fetch_creator_info_query(self) -> TiktokResponsePublishQueryCreatorInfo | None:
        query_creator_url = f"{self._base_url}/v2/post/publish/creator_info/query/"
        headers = {
            "Content-Type": "application/json; charset=UTF-8",
            "Authorization": "Bearer " + await self._get_user_token_bearer_credentials(self._tiktok_user_openid),
        }
        async with get_default_client() as client:
            response = await client.post(url=query_creator_url, headers=headers)
            response_publish_query_creator_info = TiktokResponsePublishQueryCreatorInfo.parse_obj(await response.json())

        logger.debug("Query Creator Info", response_publish_query_creator_info=response_publish_query_creator_info)
        return response_publish_query_creator_info

    @staticmethod
    def _file_sender(
        file_name: str,
        chunk_size_bytes: int,
    ):
        with open(file_name, "rb") as f:
            while True:
                chunk = f.read(chunk_size_bytes)
                if not chunk:  # Break the loop if no more data is left to read
                    break
                yield chunk

    async def upload_video(
        self,
        video_path: str,
        title: str = None,
    ) -> str | None:
        access_token = await self.refresh_token()
        auth_header = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        }

        file_size_bytes = pathlib.Path(video_path).stat().st_size
        chunk_size_64mb_in_bytes = 67108864

        upload_data = []
        first_byte = 0
        last_byte = 0
        for current_chunk in self._file_sender(file_name=video_path, chunk_size_bytes=chunk_size_64mb_in_bytes):
            last_byte = last_byte + len(current_chunk)
            upload_data.append(
                {
                    "total_byte": file_size_bytes,
                    "first_byte": first_byte,
                    "last_byte": last_byte - 1,
                    "data": current_chunk,
                }
            )

            first_byte = first_byte + len(current_chunk)

        chunk_size = math.floor(file_size_bytes / len(upload_data))

        publish_video_init_url = f"{self._base_url}/v2/post/publish/inbox/video/init/"

        data = json.dumps(
            {
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": int(file_size_bytes),
                    "chunk_size": chunk_size,
                    "total_chunk_count": int(len(upload_data)),
                }
            }
        )

        async with get_default_client() as client:
            response = await client.post(url=publish_video_init_url, headers=auth_header, data=data)
            response_body = await response.json()
            response_publish_video_init_url = TiktokResponsePublishVideoInitUrl.parse_obj(response_body)

        logger.debug("publish_video_init", response_publish_video_init_url=response_publish_video_init_url)

        async with get_default_client() as client:
            for video_data in upload_data:
                content_length = str(len(video_data["data"]))
                content_range = (
                    f"{str(video_data['first_byte'])}-{str(video_data['last_byte'])}/{str(video_data['total_byte'])}"
                )
                content_video_headers = {
                    "Content-Type": "video/mp4",
                    "Content-Length": content_length,
                    "Content-Range": f"bytes {content_range}",
                }
                response = await client.put(
                    url=response_publish_video_init_url.data.upload_url,
                    headers=content_video_headers,
                    data=video_data["data"],
                )
                logger.debug("response_chunk:", status=response.status)

        publish_video_init_url = f"{self._base_url}/v2/post/publish/status/fetch/"

        publish_id = response_publish_video_init_url.data.publish_id
        data = json.dumps(
            {
                "publish_id": publish_id,
            }
        )

        async with get_default_client() as client:
            response = await client.post(url=publish_video_init_url, headers=auth_header, data=data)
            publish_status_response = await response.json()

        logger.debug("publish status:", response=publish_status_response)
        return publish_id
