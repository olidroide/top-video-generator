"""Application settings using Pydantic v2."""

from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, cast

from pydantic import SecretStr, StringConstraints, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.shared.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
logger = get_logger(__name__)
RequiredSetting = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class Environment(StrEnum):
    PRODUCTION = "production"
    DEVELOPMENT = "development"


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(PROJECT_ROOT / ".env"), str(PROJECT_ROOT / ".env.local")),
        env_file_encoding="utf-8",
        env_prefix="TOP_MUSIC_",
        case_sensitive=False,
        extra="ignore",
    )

    env: Environment = Environment.PRODUCTION
    days_between_top: int = 7
    app_secret_key: str | None = None
    admin_password: str | None = None
    use_certifi: bool = False
    ca_bundle_file: str | None = None
    cpu_workers: int = 0
    threads_workers: int = 1
    log_file_path: str = "logs/top_music.log"
    scheduler_timezone: str | None = None
    scheduler_poll_interval_seconds: int = 60
    scheduler_heartbeat_file: str = "run/top-video-generator-scheduler-heartbeat.json"
    scheduler_heartbeat_stale_seconds: int = 10800
    scheduler_lock_file: str = "run/top-video-generator-scheduler.lock"
    scheduler_fetch_hour: int = 15
    scheduler_fetch_minute: int = 0
    scheduler_vertical_publish_hour: int = 16
    scheduler_vertical_publish_minute: int = 0
    scheduler_weekly_publish_hour: int = 17
    scheduler_weekly_publish_minute: int = 0
    scheduler_weekly_publish_day_of_week: int = 5

    yt_client_secret_file: str | None = None
    yt_redirect_uri: str | None = None
    yt_search_region_code: RequiredSetting
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
    instagram_client_password: SecretStr | None = None
    instagram_client_session_file: str | None = None

    db_timeseries_file: str = "db/db_timeseries.csv"
    db_video_file: str = "db/db_video.json"
    db_auth_file: str = "db/db_auth.json"
    db_release_file: str = "db/db_release.json"
    # Deprecated legacy shared store path. Keep for backward compatibility only.
    db_data_file: str = "db/db_data.json"

    video_template_end_screen_file: str | None = None
    video_template_start_screen_file: str | None = None
    video_template_file: str | None = None
    video_template_vertical_file: str | None = None
    video_template_thumbnail_file: str | None = None
    video_template_thumbnail_font_file: str | None = None
    video_generated_folder: str = "videos"

    @model_validator(mode="before")
    @classmethod
    def log_missing_required_settings(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        settings_data = cast("dict[str, object]", data)
        region_code = settings_data.get("yt_search_region_code")
        if region_code is None or not str(region_code).strip():
            logger.error(
                "settings.missing_required_value",
                setting="TOP_MUSIC_YT_SEARCH_REGION_CODE",
            )
        return settings_data

    @field_validator("yt_search_region_code")
    @classmethod
    def normalize_yt_search_region_code(cls, value: str) -> str:
        return value.upper()

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
    settings_factory = cast("Callable[[], AppSettings]", AppSettings)
    return settings_factory()
