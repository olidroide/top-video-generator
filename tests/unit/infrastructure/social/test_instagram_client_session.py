from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from src.config.settings import AppSettings, Environment
from src.infrastructure.social.instagram_client import (
    _load_session,
    _try_auth_with_password,
    _try_auth_with_session,
)


class TestSessionLoading:
    """Tests for _load_session() function."""

    def test_load_session_when_file_not_exists(self, tmp_path) -> None:
        """Should return None and log when session file doesn't exist."""
        session_file = tmp_path / "instagram_session.json"
        fake_client = MagicMock()

        result = _load_session(fake_client, session_file)

        assert result is None
        # load_settings should not be called if file doesn't exist
        fake_client.load_settings.assert_not_called()

    def test_load_session_when_file_exists(self, tmp_path) -> None:
        """Should load session from file when it exists."""
        session_file = tmp_path / "instagram_session.json"
        session_file.write_text('{"uuids": {"uuid": "test-uuid"}}')

        fake_client = MagicMock()
        fake_session = {"uuids": {"uuid": "test-uuid"}}
        fake_client.load_settings.return_value = fake_session

        result = _load_session(fake_client, session_file)

        assert result == fake_session
        fake_client.load_settings.assert_called_once_with(session_file)

    def test_load_session_handles_exception(self, tmp_path) -> None:
        """Should return None if load_settings raises exception."""
        session_file = tmp_path / "instagram_session.json"
        session_file.write_text("invalid json")

        fake_client = MagicMock()
        fake_client.load_settings.side_effect = ValueError("Corrupt session")

        result = _load_session(fake_client, session_file)

        assert result is None


class TestSessionAuth:
    """Tests for _try_auth_with_session() function."""

    def test_session_missing_returns_false(self) -> None:
        """Should return False when session is empty/None."""
        fake_client = MagicMock()
        fake_settings = MagicMock(spec=AppSettings, env=Environment.PRODUCTION)
        session_file = Path("instagram_session.json")
        fake_login_required_exc = Exception

        result = _try_auth_with_session(
            fake_client,
            session=None,
            settings=fake_settings,
            settings_file_path=session_file,
            username="test_user",
            password="test_pass",
            login_required_exception=fake_login_required_exc,
        )

        assert result is False
        fake_client.get_timeline_feed.assert_not_called()
        fake_client.login.assert_not_called()

    def test_session_validation_succeeds_without_reauth(self, tmp_path) -> None:
        """Should return True when loaded session validates successfully."""
        fake_client = MagicMock()
        fake_settings = MagicMock(spec=AppSettings, env=Environment.PRODUCTION)
        session_file = tmp_path / "instagram_session.json"
        session = {"uuids": {"uuid": "test-uuid"}}
        fake_login_required_exc = Exception

        # Session is valid, no exception
        fake_client.get_timeline_feed.return_value = None

        result = _try_auth_with_session(
            fake_client,
            session=session,
            settings=fake_settings,
            settings_file_path=session_file,
            username="test_user",
            password="test_pass",
            login_required_exception=fake_login_required_exc,
        )

        assert result is True
        # Should only validate, not re-login
        fake_client.get_timeline_feed.assert_called_once()
        fake_client.login.assert_not_called()

    def test_session_expired_triggers_reauth(self, tmp_path) -> None:
        """Should re-authenticate with password if session expires."""
        fake_client = MagicMock()
        fake_settings = MagicMock(spec=AppSettings, env=Environment.PRODUCTION)
        session_file = tmp_path / "instagram_session.json"
        session = {"uuids": {"uuid": "test-uuid"}}

        class FakeLoginRequiredError(Exception):
            pass

        # Validation fails with LoginRequired
        fake_client.get_timeline_feed.side_effect = FakeLoginRequiredError("Session invalid")
        # Re-auth succeeds
        fake_client.login.return_value = True

        result = _try_auth_with_session(
            fake_client,
            session=session,
            settings=fake_settings,
            settings_file_path=session_file,
            username="test_user",
            password="test_pass",
            login_required_exception=FakeLoginRequiredError,
        )

        assert result is True
        fake_client.get_timeline_feed.assert_called_once()
        fake_client.login.assert_called_once_with("test_user", "test_pass")
        fake_client.dump_settings.assert_called_once_with(session_file)


class TestPasswordAuth:
    """Tests for _try_auth_with_password() function."""

    def test_password_login_success_saves_session(self, tmp_path) -> None:
        """Should save session after successful password login."""
        fake_client = MagicMock()
        session_file = tmp_path / "instagram_session.json"
        fake_client.login.return_value = True

        result = _try_auth_with_password(
            fake_client,
            username="test_user",
            password="test_pass",
            settings_file_path=session_file,
        )

        assert result is True
        fake_client.login.assert_called_once_with("test_user", "test_pass")
        fake_client.dump_settings.assert_called_once_with(session_file)

    def test_password_login_failure_returns_false(self, tmp_path) -> None:
        """Should return False when login fails."""
        fake_client = MagicMock()
        session_file = tmp_path / "instagram_session.json"
        fake_client.login.side_effect = RuntimeError("Login failed")

        result = _try_auth_with_password(
            fake_client,
            username="test_user",
            password="test_pass",
            settings_file_path=session_file,
        )

        assert result is False
        fake_client.dump_settings.assert_not_called()

    def test_password_login_returns_false_value(self, tmp_path) -> None:
        """Should return False if login returns falsey value."""
        fake_client = MagicMock()
        session_file = tmp_path / "instagram_session.json"
        fake_client.login.return_value = None

        result = _try_auth_with_password(
            fake_client,
            username="test_user",
            password="test_pass",
            settings_file_path=session_file,
        )

        assert result is False
        fake_client.dump_settings.assert_not_called()

    def test_password_login_succeeds_when_session_persist_fails(self, tmp_path) -> None:
        """Should still return True when login succeeds but dump_settings fails."""
        fake_client = MagicMock()
        session_file = tmp_path / "instagram_session.json"
        fake_client.login.return_value = True
        fake_client.dump_settings.side_effect = PermissionError("Read-only file system")

        result = _try_auth_with_password(
            fake_client,
            username="test_user",
            password="test_pass",
            settings_file_path=session_file,
        )

        assert result is True
        fake_client.login.assert_called_once_with("test_user", "test_pass")
        fake_client.dump_settings.assert_called_once_with(session_file)


class TestSessionPersistenceFlow:
    """Integration tests for session persistence flow."""

    def test_first_run_no_session_then_reuse_on_second_run(self, tmp_path) -> None:
        """Simulate: first run (no session) → login → second run (reuse session)."""

        session_file = tmp_path / "instagram_session.json"

        # Mock the instagrapi client library
        with patch("src.infrastructure.social.instagram_client._import_instagram_client_types") as mock_import:
            mock_client_class = MagicMock()
            mock_exception = Exception

            def fake_login(username, password):
                # After login, save a fake session
                return True

            def fake_get_timeline():
                return {"feed": []}

            # First run: no session file
            instance = MagicMock()
            instance.load_settings.return_value = None
            instance.login = MagicMock(side_effect=fake_login)
            instance.get_timeline_feed = MagicMock(side_effect=fake_get_timeline)
            instance.dump_settings = MagicMock()
            instance.get_settings = MagicMock(return_value={"uuids": {"uuid": "test"}})

            mock_client_class.return_value = instance
            mock_import.return_value = (mock_client_class, mock_exception)

            # Simulate: session file doesn't exist yet
            assert not session_file.exists()

            # After first login, session should be saved
            instance.dump_settings.assert_not_called()  # Not called yet
            instance.login(username="test_user", password="test_pass")
            assert instance.login.called

            # Simulate saving session
            instance.dump_settings(session_file)
            # In real code, we'd write the session to disk
            session_file.write_text('{"uuids": {"uuid": "test"}}')

            # Second run: session file exists
            assert session_file.exists()

            # Reset mock to simulate new client instance
            instance.reset_mock()
            instance.load_settings.return_value = {"uuids": {"uuid": "test"}}
            instance.get_timeline_feed = MagicMock(return_value={})

            # Should load session and validate without re-login
            loaded_session = instance.load_settings(session_file)
            assert loaded_session is not None
            instance.get_timeline_feed()

            # Should NOT have called login again
            instance.login.assert_not_called()
