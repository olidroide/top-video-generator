from enum import Enum
from functools import lru_cache
from pathlib import Path

from pydantic import BaseSettings


class Environment(str, Enum):
    PRODUCTION = "production"
    DEVELOPMENT = "development"


class AppSettings(BaseSettings):
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        env_prefix = "TOP_MUSIC_"
        case_sensitive = False

    env: Environment = Environment.PRODUCTION
    days_between_top: int = 7
    app_secret_key: str
    cpu_workers: int = 0
    threads_workers: int = 1
    log_file_path: str = "top_music.log"

    yt_client_secret_file: str
    yt_redirect_uri: str
    yt_search_region_code: str
    yt_search_language_code: str
    yt_search_category_code: str
    yt_title_template: str = ""
    yt_description_template: str = ""
    yt_playlist_id_daily: str = None
    yt_playlist_id_weekly: str = None
    yt_auth_user_id: str = None
    yt_tags: str = ""

    tiktok_client_key: str
    tiktok_client_secret: str
    tiktok_redirect_uri: str
    tiktok_app_id: str
    tiktok_user_openid: str

    db_timeseries_file: str
    db_data_file: str

    video_template_end_screen_file: str
    video_template_start_screen_file: str
    video_template_file: str
    video_template_vertical_file: str
    video_template_thumbnail_file: str
    video_template_thumbnail_font_file: str
    video_generated_folder: str

    @property
    def is_production_env(self) -> bool:
        return self.env == Environment.PRODUCTION


@lru_cache()
def get_app_settings() -> AppSettings:
    return AppSettings(_env_file=str(Path(__file__).parent / ".env"))
