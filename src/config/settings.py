"""Application settings using Pydantic v2."""

from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Environment(StrEnum):
    PRODUCTION = "production"
    DEVELOPMENT = "development"


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        env_prefix="TOP_MUSIC_",
        case_sensitive=False,
        extra="ignore",
    )

    env: Environment = Environment.PRODUCTION
    days_between_top: int = 7
    app_secret_key: str | None = None
    cpu_workers: int = 0
    threads_workers: int = 1
    log_file_path: str = "top_music.log"

    yt_client_secret_file: str | None = None
    yt_redirect_uri: str | None = None
    yt_search_region_code: str | None = None
    yt_search_language_code: str | None = None
    yt_search_category_code: str | None = None
    yt_title_template: str = ""
    yt_description_template: str = ""
    yt_playlist_id_daily: str | None = None
    yt_playlist_id_weekly: str | None = None
    yt_playlist_id_links_original: str | None = None
    yt_auth_user_id: str | None = None
    yt_tags: str = ""

    tiktok_client_key: str | None = None
    tiktok_client_secret: str | None = None
    tiktok_redirect_uri: str | None = None
    tiktok_app_id: str | None = None
    tiktok_user_openid: str | None = None

    spotify_client_id: str | None = None
    spotify_client_secret: str | None = None
    spotify_redirect_uri: str | None = None
    spotify_user_id: str | None = None
    spotify_playlist_original: str | None = None

    instagram_client_username: str | None = None
    instagram_client_password: str | None = None
    instagram_client_session_file: str | None = None

    db_timeseries_file: str = "db/db_timeseries.csv"
    db_data_file: str = "db/db_data.json"

    video_template_end_screen_file: str | None = None
    video_template_start_screen_file: str | None = None
    video_template_file: str | None = None
    video_template_vertical_file: str | None = None
    video_template_thumbnail_file: str | None = None
    video_template_thumbnail_font_file: str | None = None
    video_generated_folder: str = "videos"

    @property
    def is_production_env(self) -> bool:
        return self.env == Environment.PRODUCTION

    @property
    def is_spotify_configured(self) -> bool:
        return all([self.spotify_client_id, self.spotify_client_secret, self.spotify_user_id])

    @property
    def is_instagram_configured(self) -> bool:
        return all([self.instagram_client_username, self.instagram_client_password])


@lru_cache
def get_app_settings() -> AppSettings:
    return AppSettings()
