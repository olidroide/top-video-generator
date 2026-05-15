"""Unit tests for web view model builders."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from src.domain.models import Platform, Release, ReleaseKind
from src.web.viewmodels import build_admin_tasks_view_model


@dataclass
class _TimeSeriesReaderStub:
    last_timestamp: datetime | None = None

    def get_last_timestamp(self) -> datetime | None:
        return self.last_timestamp


@dataclass
class _ReleaseStoreStub:
    releases_by_client: dict[str, Release | None]
    requested_client_ids: list[str] = field(default_factory=list)

    def get_release(self, platform: str, client_id: str, release_kind: str | None = None) -> Release | None:
        assert platform == Platform.YOUTUBE.value
        assert release_kind == ReleaseKind.WEEKLY_HORIZONTAL.value
        self.requested_client_ids.append(client_id)
        return self.releases_by_client.get(client_id)


def _weekly_task(tasks_vm):
    return next(task for task in tasks_vm.tasks if task.name == "Weekly Horizontal (YouTube)")


def test_build_admin_tasks_view_model_falls_back_to_default_client_id(monkeypatch) -> None:
    monkeypatch.setenv("TOP_MUSIC_YT_SEARCH_REGION_CODE", "ES")
    monkeypatch.setenv("TOP_MUSIC_YT_AUTH_USER_ID", "configured-client")

    from src.config.settings import get_app_settings

    get_app_settings.cache_clear()

    try:
        release_repo = _ReleaseStoreStub(
            releases_by_client={
                "configured-client": None,
                "default": Release(
                    platform=Platform.YOUTUBE.value,
                    client_id="default",
                    release_kind=ReleaseKind.WEEKLY_HORIZONTAL.value,
                    release_id="yt-123",
                    published_at=(datetime.now(UTC) - timedelta(hours=2)).timestamp(),
                ),
            }
        )

        tasks_vm = build_admin_tasks_view_model(_TimeSeriesReaderStub(), release_repo)
        weekly_task = _weekly_task(tasks_vm)

        assert release_repo.requested_client_ids == ["configured-client", "default"]
        assert weekly_task.source == "release"
        assert weekly_task.last_run_label != "Never"
    finally:
        get_app_settings.cache_clear()


def test_build_admin_tasks_view_model_weekly_not_stale_before_7_days(monkeypatch) -> None:
    monkeypatch.setenv("TOP_MUSIC_YT_SEARCH_REGION_CODE", "ES")
    monkeypatch.setenv("TOP_MUSIC_YT_AUTH_USER_ID", "configured-client")

    from src.config.settings import get_app_settings

    get_app_settings.cache_clear()

    try:
        release_repo = _ReleaseStoreStub(
            releases_by_client={
                "configured-client": Release(
                    platform=Platform.YOUTUBE.value,
                    client_id="configured-client",
                    release_kind=ReleaseKind.WEEKLY_HORIZONTAL.value,
                    release_id="yt-abc",
                    published_at=(datetime.now(UTC) - timedelta(hours=48)).timestamp(),
                )
            }
        )

        tasks_vm = build_admin_tasks_view_model(_TimeSeriesReaderStub(), release_repo)
        weekly_task = _weekly_task(tasks_vm)

        assert weekly_task.older_than_24h is False
        assert weekly_task.warning_message is None
    finally:
        get_app_settings.cache_clear()


def test_build_admin_tasks_view_model_weekly_stale_after_7_days(monkeypatch) -> None:
    monkeypatch.setenv("TOP_MUSIC_YT_SEARCH_REGION_CODE", "ES")
    monkeypatch.setenv("TOP_MUSIC_YT_AUTH_USER_ID", "configured-client")

    from src.config.settings import get_app_settings

    get_app_settings.cache_clear()

    try:
        release_repo = _ReleaseStoreStub(
            releases_by_client={
                "configured-client": Release(
                    platform=Platform.YOUTUBE.value,
                    client_id="configured-client",
                    release_kind=ReleaseKind.WEEKLY_HORIZONTAL.value,
                    release_id="yt-old",
                    published_at=(datetime.now(UTC) - timedelta(days=8)).timestamp(),
                )
            }
        )

        tasks_vm = build_admin_tasks_view_model(_TimeSeriesReaderStub(), release_repo)
        weekly_task = _weekly_task(tasks_vm)

        assert weekly_task.older_than_24h is True
        assert weekly_task.warning_message == "No weekly publish in 7+ days"
    finally:
        get_app_settings.cache_clear()
