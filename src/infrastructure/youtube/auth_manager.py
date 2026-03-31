"""YouTube authentication and service bootstrap helpers."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, ClassVar

import aiohttp
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.discovery_cache.base import Cache


@asynccontextmanager
async def get_default_client() -> AsyncIterator[aiohttp.ClientSession]:
    """Return a default aiohttp session for generic API requests."""
    conn = None
    async with aiohttp.ClientSession(
        connector=conn,
        headers={"Accept": "application/json"},
        timeout=aiohttp.ClientTimeout(total=30),
    ) as client:
        yield client


class MemoryCache(Cache):
    """In-memory cache for Google discovery documents."""

    _CACHE: ClassVar[dict[str, bytes]] = {}

    def get(self, url: str) -> bytes | None:
        return MemoryCache._CACHE.get(url)

    def set(self, url: str, content: bytes) -> None:
        MemoryCache._CACHE[url] = content


class YouTubeAuthManager:
    """Manages OAuth2 flow and authenticated YouTube service creation."""

    def __init__(
        self,
        *,
        client_secret_file: str,
        redirect_uri: str,
        service_name: str,
        service_version: str,
        cache: MemoryCache,
    ) -> None:
        self._client_secret_file = client_secret_file
        self._redirect_uri = redirect_uri
        self._service_name = service_name
        self._service_version = service_version
        self._cache = cache

    def _get_flow(self) -> Flow:
        flow = Flow.from_client_secrets_file(
            self._client_secret_file,
            scopes=[
                "https://www.googleapis.com/auth/youtube.upload",
                "https://www.googleapis.com/auth/youtube",
                "https://www.googleapis.com/auth/youtube.force-ssl",
                "https://www.googleapis.com/auth/youtube.readonly",
            ],
        )
        flow.redirect_uri = self._redirect_uri
        return flow

    def get_authentication_url(self) -> str:
        flow = self._get_flow()
        authorization_url, _state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
        )
        return authorization_url

    def exchange_code_authentication(self, url_requested: str) -> dict[str, str | list[str] | None]:
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

    def build_authenticated_service(self, credentials_payload: dict[str, Any]) -> Any:
        credentials = Credentials(**credentials_payload)
        return build(
            serviceName=self._service_name,
            version=self._service_version,
            credentials=credentials,
            cache=self._cache,
        )


__all__ = ["MemoryCache", "YouTubeAuthManager", "get_default_client"]
