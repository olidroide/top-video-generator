from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest
from pydantic import ValidationError
from pydantic_settings import SettingsConfigDict

import src.config.settings as settings_module
from src.config.settings import PROJECT_ROOT, AppSettings, Environment


def _load_settings_from_env_files(*env_files: Path) -> AppSettings:
    class _TestSettings(AppSettings):
        model_config = SettingsConfigDict(
            env_file=tuple(str(path) for path in env_files),
            env_file_encoding="utf-8",
            env_prefix="TOP_MUSIC_",
            case_sensitive=False,
            extra="ignore",
        )

    return _TestSettings()  # pyright: ignore[reportCallIssue]


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
                "TOP_MUSIC_YT_SEARCH_REGION_CODE=ES",
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
        "TOP_MUSIC_YT_SEARCH_REGION_CODE",
        "TOP_MUSIC_YT_CLIENT_SECRET_FILE",
        "TOP_MUSIC_DB_DATA_FILE",
    ):
        monkeypatch.delenv(env_var, raising=False)

    settings = _load_settings_from_env_files(base_env, local_env)

    assert settings.env is Environment.DEVELOPMENT
    assert settings.log_file_path == "logs/override.log"
    assert Path(settings.yt_client_secret_file or "") == Path("secrets/yt_client_secret.json")
    assert Path(settings.db_data_file) == Path("db/db_data.json")
    assert Path(settings.db_video_file) == Path("db/db_video.json")
    assert Path(settings.db_auth_file) == Path("db/db_auth.json")
    assert Path(settings.db_release_file) == Path("db/db_release.json")


def test_settings_tolerate_missing_optional_local_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base_env = tmp_path / ".env"
    base_env.write_text(
        "\n".join(
            [
                "TOP_MUSIC_YT_SEARCH_REGION_CODE=ES",
                "TOP_MUSIC_INSTAGRAM_CLIENT_SESSION_FILE=secrets/instagram_session.json",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    for env_var in (
        "TOP_MUSIC_YT_SEARCH_REGION_CODE",
        "TOP_MUSIC_INSTAGRAM_CLIENT_SESSION_FILE",
        "TOP_MUSIC_INSTAGRAM_DEV_USE_CERTIFI",
    ):
        monkeypatch.delenv(env_var, raising=False)

    settings = _load_settings_from_env_files(base_env, tmp_path / ".env.local")

    assert Path(settings.instagram_client_session_file or "") == Path("secrets/instagram_session.json")
    assert settings.instagram_dev_use_certifi is False


def test_settings_load_instagram_dev_use_certifi_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base_env = tmp_path / ".env"
    base_env.write_text(
        "\n".join(
            [
                "TOP_MUSIC_YT_SEARCH_REGION_CODE=ES",
                "TOP_MUSIC_INSTAGRAM_DEV_USE_CERTIFI=true",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    for env_var in (
        "TOP_MUSIC_YT_SEARCH_REGION_CODE",
        "TOP_MUSIC_INSTAGRAM_DEV_USE_CERTIFI",
    ):
        monkeypatch.delenv(env_var, raising=False)

    settings = _load_settings_from_env_files(base_env, tmp_path / ".env.local")

    assert settings.instagram_dev_use_certifi is True


def test_settings_require_youtube_region_code_and_log_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_env = tmp_path / ".env"
    base_env.write_text("TOP_MUSIC_ENV=development\n", encoding="utf-8")

    for env_var in ("TOP_MUSIC_ENV", "TOP_MUSIC_YT_SEARCH_REGION_CODE"):
        monkeypatch.delenv(env_var, raising=False)

    log_mock = Mock()
    monkeypatch.setattr(settings_module, "logger", log_mock)

    with pytest.raises(ValidationError) as exc_info:
        _load_settings_from_env_files(base_env, tmp_path / ".env.local")

    assert any(error["loc"] == ("yt_search_region_code",) for error in exc_info.value.errors())
    log_mock.error.assert_called_once_with(
        "settings.missing_required_value",
        setting="TOP_MUSIC_YT_SEARCH_REGION_CODE",
    )
