"""Unit tests for web view model builders."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from src.application.get_admin_task_status_use_case import TaskStatusResult
from src.domain.models import IntegrationCheckResult, IntegrationCheckStatus, IntegrationPlatform, Release
from src.web.viewmodels import build_admin_publishers_view_model, build_admin_tasks_view_model


def _task(name: str, tasks_vm):
    return next(task for task in tasks_vm.tasks if task.name == name)


def test_build_admin_tasks_view_model_fetch_stale_after_24_hours() -> None:
    now = datetime.now(UTC)
    result = TaskStatusResult(
        fetch_last_timestamp=(now - timedelta(hours=25)).timestamp(),
        daily_last_timestamp=None,
        weekly_last_timestamp=None,
        latest_status_by_method={"fetch": "success"},
    )

    tasks_vm = build_admin_tasks_view_model(result)
    fetch_task = _task("Fetch Data", tasks_vm)

    assert fetch_task.older_than_24h is True
    assert fetch_task.warning_message == "No videos fetched in 24+ hours"


def test_build_admin_tasks_view_model_daily_stale_after_24_hours() -> None:
    now = datetime.now(UTC)
    result = TaskStatusResult(
        fetch_last_timestamp=None,
        daily_last_timestamp=(now - timedelta(hours=26)).timestamp(),
        weekly_last_timestamp=None,
        latest_status_by_method={"daily": "success"},
    )

    tasks_vm = build_admin_tasks_view_model(result)
    daily_task = _task("Daily Vertical Videos", tasks_vm)

    assert daily_task.older_than_24h is True
    assert daily_task.warning_message == "No daily publish in 24+ hours"


def test_build_admin_tasks_view_model_weekly_stale_after_7_days() -> None:
    now = datetime.now(UTC)
    result = TaskStatusResult(
        fetch_last_timestamp=None,
        daily_last_timestamp=None,
        weekly_last_timestamp=(now - timedelta(days=8)).timestamp(),
        latest_status_by_method={"weekly": "success"},
    )

    tasks_vm = build_admin_tasks_view_model(result)
    weekly_task = _task("Weekly Horizontal (YouTube)", tasks_vm)

    assert weekly_task.older_than_24h is True
    assert weekly_task.warning_message == "No weekly publish in 7+ days"


def test_build_admin_tasks_view_model_non_youtube_weekly_not_applicable() -> None:
    result = TaskStatusResult(
        fetch_last_timestamp=None,
        daily_last_timestamp=None,
        weekly_last_timestamp=None,
        latest_status_by_method={},
    )

    tasks_vm = build_admin_tasks_view_model(result)

    for platform_name in ("TIKTOK", "INSTAGRAM"):
        task = _task(f"Weekly Horizontal ({platform_name})", tasks_vm)
        assert task.applicable is False
        assert task.last_run_label == "Not applicable"


def test_build_admin_tasks_view_model_daily_failed_recommends_retry_and_shows_details() -> None:
    now = datetime.now(UTC)
    result = TaskStatusResult(
        fetch_last_timestamp=None,
        daily_last_timestamp=None,
        weekly_last_timestamp=None,
        latest_status_by_method={"daily": "failed"},
        latest_error_by_method={"daily": "challenge_required"},
        daily_publish_timestamps_by_platform={
            "YOUTUBE": (now - timedelta(hours=2)).timestamp(),
            "INSTAGRAM": (now - timedelta(hours=26)).timestamp(),
        },
        latest_video_artifact_path="videos/20260515/20260515_vertical_format.mp4",
        latest_video_artifact_timestamp=(now - timedelta(hours=1)).timestamp(),
    )

    tasks_vm = build_admin_tasks_view_model(result)
    daily_task = _task("Daily Vertical Videos", tasks_vm)

    assert daily_task.action_label == "Retry Daily"
    assert daily_task.warning_message == "Last daily run failed. Retry recommended."
    assert daily_task.last_error == "challenge_required"
    assert daily_task.source == "videos_folder"
    assert any(row.startswith("Last processed video:") for row in daily_task.detail_rows)
    assert any("Artifact path: videos/20260515/20260515_vertical_format.mp4" in row for row in daily_task.detail_rows)
    assert any(row.startswith("YOUTUBE:") for row in daily_task.detail_rows)
    assert any(row.startswith("INSTAGRAM:") for row in daily_task.detail_rows)
    assert any(row == "TIKTOK: Never" for row in daily_task.detail_rows)


def test_build_admin_tasks_view_model_running_methods_shows_is_running() -> None:
    result = TaskStatusResult(
        fetch_last_timestamp=None,
        daily_last_timestamp=None,
        weekly_last_timestamp=None,
        latest_status_by_method={"fetch": "queued"},
        running_methods={"fetch"},
    )

    tasks_vm = build_admin_tasks_view_model(result)
    fetch_task = _task("Fetch Data", tasks_vm)
    daily_task = _task("Daily Vertical Videos", tasks_vm)

    assert fetch_task.is_running is True
    assert daily_task.is_running is False
    assert tasks_vm.any_running is True


def test_build_admin_tasks_view_model_no_running_tasks() -> None:
    now = datetime.now(UTC)
    result = TaskStatusResult(
        fetch_last_timestamp=now.timestamp(),
        daily_last_timestamp=now.timestamp(),
        weekly_last_timestamp=None,
        latest_status_by_method={"fetch": "success", "daily": "success"},
        running_methods=set(),
    )

    tasks_vm = build_admin_tasks_view_model(result)

    assert tasks_vm.any_running is False
    for task in tasks_vm.tasks:
        assert task.is_running is False


def test_build_admin_tasks_view_model_enriches_timeline_with_run_and_duration() -> None:
    now = datetime.now(UTC)
    queued_at = now - timedelta(minutes=3)
    success_at = now - timedelta(minutes=1)

    result = TaskStatusResult(
        fetch_last_timestamp=None,
        daily_last_timestamp=None,
        weekly_last_timestamp=None,
        timeline_data={
            "fetch": [
                {
                    "status": "queued",
                    "timestamp": queued_at.timestamp(),
                    "error_message": None,
                },
                {
                    "status": "success",
                    "timestamp": success_at.timestamp(),
                    "error_message": None,
                },
            ]
        },
    )

    tasks_vm = build_admin_tasks_view_model(result)
    fetch_events = tasks_vm.timeline_data["fetch"]

    assert len(fetch_events) == 2
    assert fetch_events[0]["run_label"] == "Run 01"
    assert fetch_events[1]["run_label"] == "Run 01"
    assert fetch_events[1]["duration_label"] is not None
    assert fetch_events[1]["duration_label"].startswith("Duration ")
    assert fetch_events[0]["relative_label"].endswith("ago")
    assert fetch_events[1]["status_label"] == "SUCCESS"


def test_build_admin_tasks_view_model_enriches_timeline_error_summary() -> None:
    now = datetime.now(UTC)
    long_error = "Timeout contacting upstream service after multiple retries and partial response corruption in payload"

    result = TaskStatusResult(
        fetch_last_timestamp=None,
        daily_last_timestamp=None,
        weekly_last_timestamp=None,
        timeline_data={
            "daily": [
                {
                    "status": "failed",
                    "timestamp": (now - timedelta(minutes=5)).timestamp(),
                    "error_message": long_error,
                }
            ]
        },
    )

    tasks_vm = build_admin_tasks_view_model(result)
    event = tasks_vm.timeline_data["daily"][0]

    assert event["error_message"] == long_error
    assert event["error_summary"] is not None
    assert len(event["error_summary"]) <= 90
    assert event["timestamp_full"].endswith("+00:00")


# ---------------------------------------------------------------------------
# build_admin_publishers_view_model — exhaustive coverage
# ---------------------------------------------------------------------------


class TestBuildAdminPublishersViewModel:
    """Exhaustive contract coverage for build_admin_publishers_view_model.

    The function assembles the admin publishers panel by querying release history
    and platform state. The critical fix changes platform lookup from slug (lowercase)
    to slug.upper() to match the stored database keys.
    """

    def _make_mock_settings(
        self, *, yt_configured: bool = True, tiktok_configured: bool = True, instagram_configured: bool = True
    ) -> MagicMock:
        """Create a settings mock with platform configuration flags."""
        settings = MagicMock()
        settings.yt_client_secret_file = "secret.json" if yt_configured else None
        settings.tiktok_cookies_file = "cookies.txt" if tiktok_configured else None
        settings.tiktok_user_openid = None
        settings.instagram_client_username = "test_user" if instagram_configured else None
        settings.instagram_client_password = MagicMock()
        return settings

    def _make_mock_state_reader(self, **enabled_by_slug) -> MagicMock:
        """Create a state_reader mock that returns is_enabled for platforms."""
        reader = MagicMock()
        reader.is_enabled = lambda slug: enabled_by_slug.get(slug, False)
        return reader

    def _make_mock_release_store(self, releases_by_platform: dict[str, Release | None]) -> MagicMock:
        """Create a release_store mock that returns releases by platform (uppercase)."""
        store = MagicMock()

        def get_latest_release(platform: str, release_kind: str | None = None):
            # Expects platform in uppercase (YouTube, TikTok, Instagram)
            return releases_by_platform.get(platform)

        store.get_latest_release = get_latest_release
        return store

    # TC-01 — Release found: slug.upper() applied correctly
    def test_release_lookup_uses_slug_upper(self) -> None:
        """Verify that platform slug is converted to uppercase for release lookup."""
        now = datetime.now(UTC)
        ts = now.timestamp()
        release = Release(platform="YOUTUBE", client_id="creator", release_id="vid-001", published_at=ts)

        state_reader = self._make_mock_state_reader(youtube=True)
        release_store = self._make_mock_release_store({"YOUTUBE": release})
        settings = self._make_mock_settings()

        result = build_admin_publishers_view_model(
            state_reader=state_reader, release_store=release_store, settings=settings
        )

        yt_publisher = next(p for p in result.publishers if p.slug == "youtube")
        assert yt_publisher.last_publish_label == "just now"

    # TC-02 — Release not found: display "Never"
    def test_release_not_found_displays_never(self) -> None:
        """When release_store returns None, last_publish_label should be 'Never'."""
        state_reader = self._make_mock_state_reader(youtube=False)
        release_store = self._make_mock_release_store({"YOUTUBE": None})
        settings = self._make_mock_settings()

        result = build_admin_publishers_view_model(
            state_reader=state_reader, release_store=release_store, settings=settings
        )

        yt_publisher = next(p for p in result.publishers if p.slug == "youtube")
        assert yt_publisher.last_publish_label == "Never"

    # TC-03 — Multiple platforms constructed correctly
    def test_all_three_platforms_present(self) -> None:
        """Verify all three platforms are built with correct names and icons."""
        state_reader = self._make_mock_state_reader(youtube=True, tiktok=True, instagram=True)
        release_store = self._make_mock_release_store({"YOUTUBE": None, "TIKTOK": None, "INSTAGRAM": None})
        settings = self._make_mock_settings()

        result = build_admin_publishers_view_model(
            state_reader=state_reader, release_store=release_store, settings=settings
        )

        assert len(result.publishers) == 3
        slugs = {p.slug for p in result.publishers}
        assert slugs == {"youtube", "tiktok", "instagram"}

        names = {p.slug: p.name for p in result.publishers}
        assert names["youtube"] == "YouTube"
        assert names["tiktok"] == "TikTok"
        assert names["instagram"] == "Instagram"

    # TC-04 — Card class transitions
    def test_card_class_inactive_when_not_configured_not_enabled(self) -> None:
        """Card is inactive when oauth_configured=False and enabled=False."""
        state_reader = self._make_mock_state_reader(youtube=False)
        release_store = self._make_mock_release_store({"YOUTUBE": None})
        settings = self._make_mock_settings(yt_configured=False)

        result = build_admin_publishers_view_model(
            state_reader=state_reader, release_store=release_store, settings=settings
        )

        yt_publisher = next(p for p in result.publishers if p.slug == "youtube")
        assert yt_publisher.card_class == "platform-card--inactive"

    def test_card_class_needs_auth_when_not_configured_but_enabled(self) -> None:
        """Card needs auth when oauth_configured=False but enabled=True."""
        state_reader = self._make_mock_state_reader(youtube=True)
        release_store = self._make_mock_release_store({"YOUTUBE": None})
        settings = self._make_mock_settings(yt_configured=False)

        result = build_admin_publishers_view_model(
            state_reader=state_reader, release_store=release_store, settings=settings
        )

        yt_publisher = next(p for p in result.publishers if p.slug == "youtube")
        assert yt_publisher.card_class == "platform-card--needs-auth"

    def test_card_class_disabled_when_configured_but_not_enabled(self) -> None:
        """Card is disabled when oauth_configured=True but enabled=False."""
        state_reader = self._make_mock_state_reader(youtube=False)
        release_store = self._make_mock_release_store({"YOUTUBE": None})
        settings = self._make_mock_settings(yt_configured=True)

        result = build_admin_publishers_view_model(
            state_reader=state_reader, release_store=release_store, settings=settings
        )

        yt_publisher = next(p for p in result.publishers if p.slug == "youtube")
        assert yt_publisher.card_class == "platform-card--disabled"

    def test_card_class_active_when_configured_and_enabled(self) -> None:
        """Card is active when oauth_configured=True and enabled=True."""
        state_reader = self._make_mock_state_reader(youtube=True)
        release_store = self._make_mock_release_store({"YOUTUBE": None})
        settings = self._make_mock_settings(yt_configured=True)

        result = build_admin_publishers_view_model(
            state_reader=state_reader, release_store=release_store, settings=settings
        )

        yt_publisher = next(p for p in result.publishers if p.slug == "youtube")
        assert yt_publisher.card_class == "platform-card--active"

    # TC-05 — Instagram auth check fields only for Instagram
    def test_auth_check_fields_only_for_instagram(self) -> None:
        """Instagram should have auth check fields; YouTube and TikTok should not."""
        state_reader = self._make_mock_state_reader(youtube=True, tiktok=True, instagram=True)
        release_store = self._make_mock_release_store({"YOUTUBE": None, "TIKTOK": None, "INSTAGRAM": None})
        settings = self._make_mock_settings()

        result = build_admin_publishers_view_model(
            state_reader=state_reader, release_store=release_store, settings=settings
        )

        yt_publisher = next(p for p in result.publishers if p.slug == "youtube")
        tiktok_publisher = next(p for p in result.publishers if p.slug == "tiktok")
        instagram_publisher = next(p for p in result.publishers if p.slug == "instagram")

        # YouTube and TikTok should not have auth check action
        assert yt_publisher.auth_check_action_label is None
        assert yt_publisher.can_run_auth_check is False
        assert tiktok_publisher.auth_check_action_label is None
        assert tiktok_publisher.can_run_auth_check is False

        # Instagram should have auth check action only if oauth_configured
        assert instagram_publisher.auth_check_action_label == "Check auth"
        assert instagram_publisher.can_run_auth_check is True

    def test_instagram_auth_check_disabled_when_not_configured(self) -> None:
        """Instagram auth check action label shows, but can_run_auth_check is False when not oauth_configured."""
        state_reader = self._make_mock_state_reader(instagram=True)
        release_store = self._make_mock_release_store({"INSTAGRAM": None})
        settings = self._make_mock_settings(instagram_configured=False)

        result = build_admin_publishers_view_model(
            state_reader=state_reader, release_store=release_store, settings=settings
        )

        instagram_publisher = next(p for p in result.publishers if p.slug == "instagram")
        assert instagram_publisher.auth_check_action_label == "Check auth"
        assert instagram_publisher.can_run_auth_check is False

    # TC-06 — Integration check result handling
    def test_integration_check_ok_status(self) -> None:
        """Check result with OK status should display VERIFIED."""
        check_ok = IntegrationCheckResult(
            platform=IntegrationPlatform.INSTAGRAM,
            status=IntegrationCheckStatus.OK,
            is_configured=True,
            is_publish_target=True,
            message="Connection successful",
        )

        state_reader = self._make_mock_state_reader(instagram=True)
        release_store = self._make_mock_release_store({"INSTAGRAM": None})
        settings = self._make_mock_settings()

        result = build_admin_publishers_view_model(
            state_reader=state_reader,
            release_store=release_store,
            settings=settings,
            check_results={"instagram": check_ok},
        )

        instagram_publisher = next(p for p in result.publishers if p.slug == "instagram")
        assert instagram_publisher.auth_check_label == "VERIFIED"
        assert instagram_publisher.auth_check_state == "on"
        assert instagram_publisher.auth_check_message == "Connection successful"

    def test_integration_check_error_status(self) -> None:
        """Check result with ERROR status should display ERROR."""
        check_error = IntegrationCheckResult(
            platform=IntegrationPlatform.INSTAGRAM,
            status=IntegrationCheckStatus.ERROR,
            is_configured=True,
            is_publish_target=True,
            message="Invalid credentials",
        )

        state_reader = self._make_mock_state_reader(instagram=True)
        release_store = self._make_mock_release_store({"INSTAGRAM": None})
        settings = self._make_mock_settings()

        result = build_admin_publishers_view_model(
            state_reader=state_reader,
            release_store=release_store,
            settings=settings,
            check_results={"instagram": check_error},
        )

        instagram_publisher = next(p for p in result.publishers if p.slug == "instagram")
        assert instagram_publisher.auth_check_label == "ERROR"
        assert instagram_publisher.auth_check_state == "off"
        assert instagram_publisher.auth_check_message == "Invalid credentials"

    def test_integration_check_not_configured_status(self) -> None:
        """Check result with NOT_CONFIGURED status should display NOT CONFIGURED."""
        check_nc = IntegrationCheckResult(
            platform=IntegrationPlatform.INSTAGRAM,
            status=IntegrationCheckStatus.NOT_CONFIGURED,
            is_configured=False,
            is_publish_target=True,
            message="Missing config",
        )

        state_reader = self._make_mock_state_reader(instagram=True)
        release_store = self._make_mock_release_store({"INSTAGRAM": None})
        settings = self._make_mock_settings()

        result = build_admin_publishers_view_model(
            state_reader=state_reader,
            release_store=release_store,
            settings=settings,
            check_results={"instagram": check_nc},
        )

        instagram_publisher = next(p for p in result.publishers if p.slug == "instagram")
        assert instagram_publisher.auth_check_label == "NOT CONFIGURED"
        assert instagram_publisher.auth_check_state == "na"
        assert instagram_publisher.auth_check_message == "Missing config"

    def test_no_check_results_yields_none_fields(self) -> None:
        """When check_results is None, auth check fields should be None."""
        state_reader = self._make_mock_state_reader(instagram=True)
        release_store = self._make_mock_release_store({"INSTAGRAM": None})
        settings = self._make_mock_settings()

        result = build_admin_publishers_view_model(
            state_reader=state_reader,
            release_store=release_store,
            settings=settings,
            check_results=None,
        )

        instagram_publisher = next(p for p in result.publishers if p.slug == "instagram")
        assert instagram_publisher.auth_check_label is None
        assert instagram_publisher.auth_check_state is None
        assert instagram_publisher.auth_check_message is None

    # TC-07 — Release timestamp formatting
    def test_release_within_24h_uses_hours_label(self) -> None:
        """Release within 24 hours should display 'N h ago' format."""
        now = datetime.now(UTC)
        ts = (now - timedelta(hours=5)).timestamp()
        release = Release(platform="YOUTUBE", client_id="creator", release_id="vid-001", published_at=ts)

        state_reader = self._make_mock_state_reader(youtube=True)
        release_store = self._make_mock_release_store({"YOUTUBE": release})
        settings = self._make_mock_settings()

        result = build_admin_publishers_view_model(
            state_reader=state_reader, release_store=release_store, settings=settings
        )

        yt_publisher = next(p for p in result.publishers if p.slug == "youtube")
        assert yt_publisher.last_publish_label == "5 h ago"

    def test_release_older_than_24h_uses_iso_format(self) -> None:
        """Release older than 24 hours should display ISO 8601 format."""
        ts = (datetime(2026, 6, 10, 14, 30, 0, tzinfo=UTC)).timestamp()
        release = Release(platform="YOUTUBE", client_id="creator", release_id="vid-001", published_at=ts)

        state_reader = self._make_mock_state_reader(youtube=True)
        release_store = self._make_mock_release_store({"YOUTUBE": release})
        settings = self._make_mock_settings()

        result = build_admin_publishers_view_model(
            state_reader=state_reader, release_store=release_store, settings=settings
        )

        yt_publisher = next(p for p in result.publishers if p.slug == "youtube")
        # ISO format with minute precision: 2026-06-10T14:30+00:00
        assert yt_publisher.last_publish_label.startswith("2026-06-10T14:30")

    def test_release_with_epoch_zero_is_not_treated_as_never(self) -> None:
        """A valid timestamp value of 0 should render as an ISO label, not 'Never'."""
        release = Release(platform="YOUTUBE", client_id="creator", release_id="vid-001", published_at=0.0)

        state_reader = self._make_mock_state_reader(youtube=True)
        release_store = self._make_mock_release_store({"YOUTUBE": release})
        settings = self._make_mock_settings()

        result = build_admin_publishers_view_model(
            state_reader=state_reader, release_store=release_store, settings=settings
        )

        yt_publisher = next(p for p in result.publishers if p.slug == "youtube")
        assert yt_publisher.last_publish_label.startswith("1970-01-01T00:00")
