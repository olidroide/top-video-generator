from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pydantic_settings import SettingsConfigDict

from src.config.settings import PROJECT_ROOT, AppSettings, Environment

if TYPE_CHECKING:
    import pytest


def test_settings_default_env_files_use_shared_env_family() -> None:
    assert AppSettings.model_config.get("env_file") == (
        str(PROJECT_ROOT / ".env"),
        str(PROJECT_ROOT / ".env.local"),
    )


def test_settings_load_env_files_in_order_with_local_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base_env = tmp_path / ".env"
    local_env = tmp_path / ".env.local"
    base_env.write_text(
        "\n".join(
            [
                "TOP_MUSIC_ENV=production",
                "TOP_MUSIC_LOG_FILE_PATH=logs/base.log",
                "TOP_MUSIC_YT_CLIENT_SECRET_FILE=secrets/yt_client_secret.json",
                "TOP_MUSIC_DB_DATA_FILE=db/db_data.json",
            ]
        ),
        encoding="utf-8",
    )
    local_env.write_text(
        "\n".join(
            [
                "TOP_MUSIC_ENV=development",
                "TOP_MUSIC_LOG_FILE_PATH=logs/override.log",
            ]
        ),
        encoding="utf-8",
    )

    for env_var in (
        "TOP_MUSIC_ENV",
        "TOP_MUSIC_LOG_FILE_PATH",
        "TOP_MUSIC_YT_CLIENT_SECRET_FILE",
        "TOP_MUSIC_DB_DATA_FILE",
    ):
        monkeypatch.delenv(env_var, raising=False)

    class _TestSettings(AppSettings):
        model_config = SettingsConfigDict(
            env_file=(str(base_env), str(local_env)),
            env_file_encoding="utf-8",
            env_prefix="TOP_MUSIC_",
            case_sensitive=False,
            extra="ignore",
        )

    settings = _TestSettings()

    assert settings.env is Environment.DEVELOPMENT
    assert settings.log_file_path == "logs/override.log"
    assert Path(settings.yt_client_secret_file or "") == Path("secrets/yt_client_secret.json")
    assert Path(settings.db_data_file) == Path("db/db_data.json")


def test_settings_tolerate_missing_optional_local_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base_env = tmp_path / ".env"
    base_env.write_text(
        "TOP_MUSIC_INSTAGRAM_CLIENT_SESSION_FILE=secrets/instagram_session.json\n",
        encoding="utf-8",
    )

    monkeypatch.delenv("TOP_MUSIC_INSTAGRAM_CLIENT_SESSION_FILE", raising=False)

    class _TestSettings(AppSettings):
        model_config = SettingsConfigDict(
            env_file=(str(base_env), str(tmp_path / ".env.local")),
            env_file_encoding="utf-8",
            env_prefix="TOP_MUSIC_",
            case_sensitive=False,
            extra="ignore",
        )

    settings = _TestSettings()

    assert Path(settings.instagram_client_session_file or "") == Path("secrets/instagram_session.json")
