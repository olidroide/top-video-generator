import random
from contextlib import asynccontextmanager
from datetime import datetime
from typing import TypeVar

import aiohttp
from src.logger import get_logger
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from pydantic import BaseModel

from src.db_client import DatabaseClient
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


class YTClient:
    YT_API_SERVICE_NAME = "youtube"
    YT_API_VERSION = "v3"

    def __init__(self) -> None:
        super().__init__()
        self._yt_client_secret_file_name: str = get_app_settings().yt_client_secret_file
        self._yt_redirect_uri: str = get_app_settings().yt_redirect_uri
        self._yt_search_region_code: str = get_app_settings().yt_search_region_code
        self._yt_search_category_code: str = get_app_settings().yt_search_category_code
        self._yt_auth_user_id: str = get_app_settings().yt_auth_user_id

    def get_authenticated_service(self):
        yt_auth = DatabaseClient().get_yt_auth(self._yt_auth_user_id)
        credentials = Credentials(**yt_auth.dict())

        return build(
            serviceName=self.YT_API_SERVICE_NAME,
            version=self.YT_API_VERSION,
            credentials=credentials,
        )

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

    def step_1_get_authentication_url(self):
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
                    hl="hi",
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

    async def get_popular_videos(
        self,
        max_results: int = 25,
    ):
        data = YTRoot.parse_obj(await self._fetch_popular_videos(max_results=max_results))
        return data

    async def get_video_details(self, video_id: str):
        data = YTRoot.parse_obj(await self._fetch_video_details(video_id=video_id))
        return data

    async def upload_video(self, video_path, title, description, thumbnail_path: str = None, playlist_id: str = None):
        try:
            youtube = self.get_authenticated_service()
            media = MediaFileUpload(video_path, chunksize=-1, resumable=True)

            video = (
                youtube.videos()
                .insert(
                    autoLevels=True,
                    notifySubscribers=True,
                    stabilize=False,
                    part="snippet,status",
                    body={
                        "snippet": {
                            "title": title,
                            "description": description,
                            "categoryId": "10",
                            "defaultAudioLanguage": "hi",
                            "tags": [
                                "top 25",
                                "top viewed songs",
                                "bollywood",
                                "songs",
                                "past 7 days",
                                "latest bollywood songs",
                                "latest hindi songs",
                                "latest punjabi songs",
                                "new romantic songs",
                                "new songs sad",
                                "love songs",
                                "romantic hits",
                                "shorts bollywood",
                                "top 5",
                                f"hindi songs {datetime.utcnow().year}",
                                "hindi songs new",
                                f"bollywood songs {datetime.utcnow().year}",
                                f"bollywood movies {datetime.utcnow().year}",
                                "hindi songs",
                                "hindi dance songs",
                                "hindi songs bollywood",
                                "New songs",
                                "Bollywood Romantic Songs",
                                "Video Song",
                            ],
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

            logger.debug("Uploaded video:", video=video["id"])

            if thumbnail_path:
                logger.debug("set thumbnail video", video=video["id"], playlist_id=thumbnail_path)

                youtube.thumbnails().set(videoId=video["id"], media_body=MediaFileUpload(thumbnail_path)).execute()

            if playlist_id:
                logger.debug("insert video into playlist", video=video["id"], playlist_id=playlist_id)

                youtube.playlistItems().insert(
                    part="snippet",
                    body={
                        "snippet": {
                            "playlistId": playlist_id,
                            "resourceId": {
                                "kind": "youtube#video",
                                "videoId": video["id"],
                            },
                        }
                    },
                ).execute()

        except HttpError as e:
            logger.error("An error occurred", error=e)
            return False
        return True


class YTClientFake(YTClient):
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

    async def upload_video(self, video_path, title, description, thumbnail_path=None):
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
    pageInfo: YTPageInfo | None


class YTVideoContentDetails(BaseModel):
    duration: str | None
    dimension: str | None  # 2d
    definition: str | None  # hd
    caption: str | None
    licensedContent: bool | None
    contentRating: dict | None
    projection: str | None  # rectangular


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
