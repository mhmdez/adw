"""Tests for Telegram integration.

Tests cover:
- TelegramConfig creation and loading
- TelegramClient request building (mocked)
- TelegramTaskState serialization
- Command handlers
- Callback query handling
- Message formatting
- State management
- Notification functions
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from adw.integrations.telegram import (
    TelegramClient,
    TelegramConfig,
    TelegramTaskState,
    _escape_html,
    _parse_simple_toml,
    format_approval_request_message,
    format_help_message,
    format_status_message,
    format_task_completed_message,
    format_task_failed_message,
    format_task_started_message,
    get_task_state,
    handle_callback_query,
    handle_status_command,
    load_telegram_state,
    make_approve_reject_keyboard,
    make_retry_keyboard,
    process_update,
    save_telegram_state,
    update_task_state,
)


# =============================================================================
# TelegramConfig Tests
# =============================================================================


class TestTelegramConfig:
    """Tests for TelegramConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default config values."""
        config = TelegramConfig(bot_token="123456789:ABC")

        assert config.bot_token == "123456789:ABC"
        assert config.chat_id is None
        assert config.poll_timeout == 30
        assert config.notification_events == ["task_started", "task_completed", "task_failed"]

    def test_custom_values(self) -> None:
        """Test config with custom values."""
        config = TelegramConfig(
            bot_token="987654321:XYZ",
            chat_id="123456789",
            notification_events=["task_completed"],
            poll_timeout=60,
        )

        assert config.bot_token == "987654321:XYZ"
        assert config.chat_id == "123456789"
        assert config.poll_timeout == 60
        assert config.notification_events == ["task_completed"]

    def test_from_env(self) -> None:
        """Test loading config from environment."""
        with patch.dict(
            os.environ,
            {
                "TELEGRAM_BOT_TOKEN": "123:ABC",
                "TELEGRAM_CHAT_ID": "999888777",
                "TELEGRAM_POLL_TIMEOUT": "45",
            },
        ):
            config = TelegramConfig.from_env()
            assert config is not None
            assert config.bot_token == "123:ABC"
            assert config.chat_id == "999888777"
            assert config.poll_timeout == 45

    def test_from_env_missing_required(self) -> None:
        """Test from_env returns None when required vars missing."""
        with patch.dict(os.environ, {}, clear=True):
            config = TelegramConfig.from_env()
            assert config is None

    def test_from_env_minimal(self) -> None:
        """Test from_env with only required token."""
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "abc:xyz"}, clear=True):
            config = TelegramConfig.from_env()
            assert config is not None
            assert config.bot_token == "abc:xyz"
            assert config.chat_id is None

    def test_from_config_file(self) -> None:
        """Test loading config from TOML file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("[telegram]\n")
            f.write('bot_token = "111222333:DEF"\n')
            f.write('chat_id = "555666777"\n')
            f.write("poll_timeout = 90\n")
            f.flush()

            config = TelegramConfig.from_config_file(Path(f.name))

            assert config is not None
            assert config.bot_token == "111222333:DEF"
            assert config.chat_id == "555666777"
            assert config.poll_timeout == 90

            os.unlink(f.name)

    def test_from_config_file_missing(self) -> None:
        """Test from_config_file returns None for missing file."""
        config = TelegramConfig.from_config_file(Path("/nonexistent/config.toml"))
        assert config is None

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        config = TelegramConfig(
            bot_token="123:ABC",
            chat_id="999888777",
            poll_timeout=60,
        )

        result = config.to_dict()
        assert result["chat_id"] == "999888777"
        assert result["poll_timeout"] == 60
        assert "notification_events" in result
        # Note: bot_token not included for security


# =============================================================================
# TelegramTaskState Tests
# =============================================================================


class TestTelegramTaskState:
    """Tests for TelegramTaskState dataclass."""

    def test_default_values(self) -> None:
        """Test default state values."""
        state = TelegramTaskState(adw_id="abc123de", chat_id=123456)

        assert state.adw_id == "abc123de"
        assert state.chat_id == 123456
        assert state.message_id is None
        assert state.user_id is None
        assert state.username is None
        assert state.description == ""
        assert state.workflow == "standard"
        assert state.model == "sonnet"
        assert state.status == "pending"

    def test_custom_values(self) -> None:
        """Test state with custom values."""
        state = TelegramTaskState(
            adw_id="def456gh",
            chat_id=789012,
            message_id=100,
            user_id=555,
            username="testuser",
            description="Test task",
            workflow="sdlc",
            model="opus",
            status="in_progress",
        )

        assert state.adw_id == "def456gh"
        assert state.chat_id == 789012
        assert state.message_id == 100
        assert state.user_id == 555
        assert state.username == "testuser"
        assert state.description == "Test task"
        assert state.workflow == "sdlc"
        assert state.model == "opus"
        assert state.status == "in_progress"

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        state = TelegramTaskState(
            adw_id="abc123de",
            chat_id=123456,
            description="Test",
        )

        result = state.to_dict()
        assert result["adw_id"] == "abc123de"
        assert result["chat_id"] == 123456
        assert result["description"] == "Test"
        assert "created_at" in result

    def test_from_dict(self) -> None:
        """Test creation from dictionary."""
        data = {
            "adw_id": "xyz789ab",
            "chat_id": 999888,
            "message_id": 50,
            "username": "alice",
            "description": "From dict",
            "workflow": "simple",
            "status": "completed",
        }

        state = TelegramTaskState.from_dict(data)
        assert state.adw_id == "xyz789ab"
        assert state.chat_id == 999888
        assert state.message_id == 50
        assert state.username == "alice"
        assert state.description == "From dict"
        assert state.workflow == "simple"
        assert state.status == "completed"

    def test_round_trip(self) -> None:
        """Test to_dict and from_dict round trip."""
        original = TelegramTaskState(
            adw_id="round123",
            chat_id=111222,
            message_id=333,
            user_id=444,
            username="bob",
            description="Round trip test",
            workflow="sdlc",
            model="haiku",
            status="awaiting_review",
        )

        restored = TelegramTaskState.from_dict(original.to_dict())

        assert restored.adw_id == original.adw_id
        assert restored.chat_id == original.chat_id
        assert restored.message_id == original.message_id
        assert restored.username == original.username
        assert restored.description == original.description
        assert restored.workflow == original.workflow
        assert restored.model == original.model
        assert restored.status == original.status


# =============================================================================
# State Management Tests
# =============================================================================


class TestStateManagement:
    """Tests for state persistence functions."""

    def test_save_and_load_state(self) -> None:
        """Test saving and loading state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "telegram_state.json"

            with patch("adw.integrations.telegram.TELEGRAM_STATE_FILE", state_file):
                with patch("adw.integrations.telegram.ADW_DIR", Path(tmpdir)):
                    # Save state
                    tasks = {
                        "abc123": TelegramTaskState(
                            adw_id="abc123",
                            chat_id=111,
                            description="Task 1",
                        ),
                        "def456": TelegramTaskState(
                            adw_id="def456",
                            chat_id=222,
                            description="Task 2",
                        ),
                    }
                    save_telegram_state(tasks)

                    # Load state
                    loaded = load_telegram_state()

                    assert len(loaded) == 2
                    assert "abc123" in loaded
                    assert "def456" in loaded
                    assert loaded["abc123"].description == "Task 1"
                    assert loaded["def456"].chat_id == 222

    def test_load_empty_state(self) -> None:
        """Test loading state when file doesn't exist."""
        with patch("adw.integrations.telegram.TELEGRAM_STATE_FILE", Path("/nonexistent/state.json")):
            state = load_telegram_state()
            assert state == {}

    def test_get_task_state(self) -> None:
        """Test getting specific task state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "telegram_state.json"

            with patch("adw.integrations.telegram.TELEGRAM_STATE_FILE", state_file):
                with patch("adw.integrations.telegram.ADW_DIR", Path(tmpdir)):
                    tasks = {
                        "abc123": TelegramTaskState(
                            adw_id="abc123",
                            chat_id=111,
                            description="Task 1",
                        ),
                    }
                    save_telegram_state(tasks)

                    result = get_task_state("abc123")
                    assert result is not None
                    assert result.adw_id == "abc123"

                    missing = get_task_state("nonexistent")
                    assert missing is None

    def test_update_task_state(self) -> None:
        """Test updating task state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "telegram_state.json"

            with patch("adw.integrations.telegram.TELEGRAM_STATE_FILE", state_file):
                with patch("adw.integrations.telegram.ADW_DIR", Path(tmpdir)):
                    tasks = {
                        "abc123": TelegramTaskState(
                            adw_id="abc123",
                            chat_id=111,
                            status="pending",
                        ),
                    }
                    save_telegram_state(tasks)

                    result = update_task_state("abc123", status="completed", message_id=999)

                    assert result is not None
                    assert result.status == "completed"
                    assert result.message_id == 999

                    # Verify persistence
                    loaded = load_telegram_state()
                    assert loaded["abc123"].status == "completed"


# =============================================================================
# Message Formatting Tests
# =============================================================================


class TestMessageFormatting:
    """Tests for message formatting functions."""

    def test_format_task_started_message(self) -> None:
        """Test task started message formatting."""
        message = format_task_started_message(
            adw_id="abc123de",
            description="Add user auth",
            workflow="sdlc",
            model="opus",
            user="alice",
        )

        assert "🚀" in message
        assert "Task Started" in message
        assert "abc123de" in message
        assert "Add user auth" in message
        assert "sdlc" in message
        assert "opus" in message
        assert "alice" in message

    def test_format_task_completed_message(self) -> None:
        """Test task completed message formatting."""
        message = format_task_completed_message(
            adw_id="abc123de",
            description="Add user auth",
            duration="5m 30s",
            pr_url="https://github.com/test/repo/pull/123",
        )

        assert "✅" in message
        assert "Task Completed" in message
        assert "abc123de" in message
        assert "5m 30s" in message
        assert "https://github.com/test/repo/pull/123" in message

    def test_format_task_failed_message(self) -> None:
        """Test task failed message formatting."""
        message = format_task_failed_message(
            adw_id="abc123de",
            description="Add user auth",
            error="Tests failed: 3 assertions",
        )

        assert "❌" in message
        assert "Task Failed" in message
        assert "abc123de" in message
        assert "Tests failed" in message

    def test_format_approval_request_message(self) -> None:
        """Test approval request message formatting."""
        message = format_approval_request_message(
            adw_id="abc123de",
            description="Add user auth",
            plan_summary="1. Create auth module\n2. Add tests",
        )

        assert "⏳" in message
        assert "Approval Required" in message
        assert "abc123de" in message
        assert "Create auth module" in message

    def test_format_status_message_empty(self) -> None:
        """Test status message with no tasks."""
        message = format_status_message([])

        assert "No active tasks" in message

    def test_format_status_message_with_tasks(self) -> None:
        """Test status message with tasks."""
        tasks = [
            {"adw_id": "abc123", "status": "in_progress", "description": "Task 1"},
            {"adw_id": "def456", "status": "completed", "description": "Task 2"},
            {"adw_id": "ghi789", "status": "failed", "description": "Task 3"},
        ]

        message = format_status_message(tasks)

        assert "Active Tasks" in message
        assert "abc123" in message
        assert "def456" in message
        assert "🟡" in message  # in_progress
        assert "✅" in message  # completed
        assert "❌" in message  # failed

    def test_format_help_message(self) -> None:
        """Test help message formatting."""
        message = format_help_message()

        assert "ADW Bot Commands" in message
        assert "/task" in message
        assert "/status" in message
        assert "/approve" in message
        assert "/reject" in message
        assert "{opus}" in message
        assert "{sdlc}" in message


# =============================================================================
# HTML Escaping Tests
# =============================================================================


class TestHtmlEscaping:
    """Tests for HTML escaping function."""

    def test_escape_ampersand(self) -> None:
        """Test escaping ampersand."""
        assert _escape_html("foo & bar") == "foo &amp; bar"

    def test_escape_less_than(self) -> None:
        """Test escaping less than."""
        assert _escape_html("a < b") == "a &lt; b"

    def test_escape_greater_than(self) -> None:
        """Test escaping greater than."""
        assert _escape_html("a > b") == "a &gt; b"

    def test_escape_multiple(self) -> None:
        """Test escaping multiple characters."""
        assert _escape_html("<script>alert('xss')</script>") == "&lt;script&gt;alert('xss')&lt;/script&gt;"

    def test_escape_preserves_normal_text(self) -> None:
        """Test normal text is preserved."""
        assert _escape_html("Hello World 123!") == "Hello World 123!"


# =============================================================================
# Inline Keyboard Tests
# =============================================================================


class TestInlineKeyboards:
    """Tests for inline keyboard creation."""

    def test_make_approve_reject_keyboard(self) -> None:
        """Test approve/reject keyboard creation."""
        keyboard = make_approve_reject_keyboard("abc123")

        assert "inline_keyboard" in keyboard
        buttons = keyboard["inline_keyboard"]

        # First row: approve and reject
        assert len(buttons[0]) == 2
        assert buttons[0][0]["text"] == "✅ Approve"
        assert buttons[0][0]["callback_data"] == "approve_abc123"
        assert buttons[0][1]["text"] == "❌ Reject"
        assert buttons[0][1]["callback_data"] == "reject_abc123"

        # Second row: details
        assert len(buttons[1]) == 1
        assert buttons[1][0]["text"] == "📋 View Details"
        assert buttons[1][0]["callback_data"] == "details_abc123"

    def test_make_retry_keyboard(self) -> None:
        """Test retry keyboard creation."""
        keyboard = make_retry_keyboard("def456")

        assert "inline_keyboard" in keyboard
        buttons = keyboard["inline_keyboard"]

        assert len(buttons[0]) == 2
        assert buttons[0][0]["text"] == "🔄 Retry"
        assert buttons[0][0]["callback_data"] == "retry_def456"
        assert buttons[0][1]["text"] == "📋 View Logs"
        assert buttons[0][1]["callback_data"] == "logs_def456"


# =============================================================================
# TelegramClient Tests
# =============================================================================


class TestTelegramClient:
    """Tests for TelegramClient class."""

    def test_init(self) -> None:
        """Test client initialization."""
        client = TelegramClient("123:ABC")
        assert client.bot_token == "123:ABC"
        assert client._rate_limit_reset == 0
        assert client._last_update_id == 0

    @patch("urllib.request.urlopen")
    def test_get_me_success(self, mock_urlopen: MagicMock) -> None:
        """Test successful getMe request."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "ok": True,
            "result": {
                "id": 123456789,
                "username": "test_bot",
                "first_name": "Test Bot",
            },
        }).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        client = TelegramClient("123:ABC")
        result = client.get_me()

        assert result is not None
        assert result["id"] == 123456789
        assert result["username"] == "test_bot"

    @patch("urllib.request.urlopen")
    def test_send_message_success(self, mock_urlopen: MagicMock) -> None:
        """Test successful message sending."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "ok": True,
            "result": {
                "message_id": 100,
                "chat": {"id": 999},
                "text": "Hello",
            },
        }).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        client = TelegramClient("123:ABC")
        result = client.send_message(999, "Hello")

        assert result is not None
        assert result["message_id"] == 100

    @patch("urllib.request.urlopen")
    def test_send_message_with_keyboard(self, mock_urlopen: MagicMock) -> None:
        """Test message sending with inline keyboard."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "ok": True,
            "result": {"message_id": 101},
        }).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        client = TelegramClient("123:ABC")
        keyboard = make_approve_reject_keyboard("abc123")
        result = client.send_message(999, "Choose", reply_markup=keyboard)

        assert result is not None

    @patch("urllib.request.urlopen")
    def test_edit_message_text(self, mock_urlopen: MagicMock) -> None:
        """Test message editing."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "ok": True,
            "result": {"message_id": 100, "text": "Updated"},
        }).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        client = TelegramClient("123:ABC")
        result = client.edit_message_text(999, 100, "Updated")

        assert result is not None
        assert result["text"] == "Updated"

    @patch("urllib.request.urlopen")
    def test_answer_callback_query(self, mock_urlopen: MagicMock) -> None:
        """Test callback query answering."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "ok": True,
            "result": True,
        }).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        client = TelegramClient("123:ABC")
        result = client.answer_callback_query("query123", "Done!")

        assert result is True

    @patch("urllib.request.urlopen")
    def test_get_updates(self, mock_urlopen: MagicMock) -> None:
        """Test getting updates."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "ok": True,
            "result": [
                {"update_id": 1, "message": {"text": "/help"}},
                {"update_id": 2, "message": {"text": "/task test"}},
            ],
        }).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        client = TelegramClient("123:ABC")
        updates = client.get_updates()

        assert len(updates) == 2
        assert updates[0]["update_id"] == 1


# =============================================================================
# Command Parsing Tests
# =============================================================================


class TestCommandParsing:
    """Tests for command parsing in process_update."""

    def test_process_update_ignores_non_command(self) -> None:
        """Test that non-command messages are ignored."""
        client = MagicMock(spec=TelegramClient)
        update = {
            "update_id": 1,
            "message": {
                "chat": {"id": 123},
                "from": {"id": 456},
                "text": "Hello there",  # Not a command
            },
        }

        process_update(client, update)

        # No send_message call should be made
        client.send_message.assert_not_called()

    def test_process_update_help_command(self) -> None:
        """Test /help command processing."""
        client = MagicMock(spec=TelegramClient)
        update = {
            "update_id": 1,
            "message": {
                "chat": {"id": 123},
                "from": {"id": 456, "username": "test"},
                "text": "/help",
            },
        }

        process_update(client, update)

        client.send_message.assert_called_once()
        call_args = client.send_message.call_args
        assert call_args[0][0] == 123  # chat_id
        assert "ADW Bot Commands" in call_args[0][1]  # message contains help text

    def test_process_update_start_command(self) -> None:
        """Test /start command processing (shows help)."""
        client = MagicMock(spec=TelegramClient)
        update = {
            "update_id": 1,
            "message": {
                "chat": {"id": 123},
                "from": {"id": 456},
                "text": "/start",
            },
        }

        process_update(client, update)

        client.send_message.assert_called_once()
        call_args = client.send_message.call_args
        assert "ADW Bot Commands" in call_args[0][1]

    def test_process_update_command_with_bot_username(self) -> None:
        """Test command with @bot_username suffix."""
        client = MagicMock(spec=TelegramClient)
        update = {
            "update_id": 1,
            "message": {
                "chat": {"id": 123},
                "from": {"id": 456},
                "text": "/help@adw_bot",
            },
        }

        process_update(client, update)

        client.send_message.assert_called_once()
        assert "ADW Bot Commands" in client.send_message.call_args[0][1]


# =============================================================================
# TOML Parsing Tests
# =============================================================================


class TestTomlParsing:
    """Tests for simple TOML parser."""

    def test_parse_basic_section(self) -> None:
        """Test parsing basic TOML section."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("[telegram]\n")
            f.write('bot_token = "123:ABC"\n')
            f.write('chat_id = "999"\n')
            f.flush()

            result = _parse_simple_toml(Path(f.name))

            assert "telegram" in result
            assert result["telegram"]["bot_token"] == "123:ABC"
            assert result["telegram"]["chat_id"] == "999"

            os.unlink(f.name)

    def test_parse_with_comments(self) -> None:
        """Test parsing TOML with comments."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("# This is a comment\n")
            f.write("[telegram]\n")
            f.write('bot_token = "abc"  # inline comment ignored\n')
            f.flush()

            result = _parse_simple_toml(Path(f.name))

            # Note: simple parser doesn't handle inline comments perfectly
            # but should still work for basic cases
            assert "telegram" in result

            os.unlink(f.name)

    def test_parse_integer_value(self) -> None:
        """Test parsing integer values."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("[telegram]\n")
            f.write("poll_timeout = 60\n")
            f.flush()

            result = _parse_simple_toml(Path(f.name))

            assert result["telegram"]["poll_timeout"] == 60

            os.unlink(f.name)

    def test_parse_boolean_value(self) -> None:
        """Test parsing boolean values."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("[telegram]\n")
            f.write("enabled = true\n")
            f.write("debug = false\n")
            f.flush()

            result = _parse_simple_toml(Path(f.name))

            assert result["telegram"]["enabled"] is True
            assert result["telegram"]["debug"] is False

            os.unlink(f.name)

    def test_parse_multiple_sections(self) -> None:
        """Test parsing multiple TOML sections."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("[telegram]\n")
            f.write('bot_token = "abc"\n')
            f.write("\n")
            f.write("[slack]\n")
            f.write('bot_token = "xyz"\n')
            f.flush()

            result = _parse_simple_toml(Path(f.name))

            assert "telegram" in result
            assert "slack" in result
            assert result["telegram"]["bot_token"] == "abc"
            assert result["slack"]["bot_token"] == "xyz"

            os.unlink(f.name)


# =============================================================================
# Integration Tests (Mocked)
# =============================================================================


class TestIntegration:
    """Integration tests with mocked dependencies."""

    @patch("adw.integrations.telegram.TelegramConfig.load")
    def test_notify_without_config(self, mock_load: MagicMock) -> None:
        """Test notification fails gracefully without config."""
        from adw.integrations.telegram import notify_task_started

        mock_load.return_value = None

        result = notify_task_started("abc123", "Test task")

        assert result is False

    @patch("adw.integrations.telegram.TelegramConfig.load")
    def test_notify_without_chat_id(self, mock_load: MagicMock) -> None:
        """Test notification fails gracefully without chat_id."""
        from adw.integrations.telegram import notify_task_started

        mock_load.return_value = TelegramConfig(
            bot_token="123:ABC",
            chat_id=None,  # No chat_id
        )

        result = notify_task_started("abc123", "Test task")

        assert result is False

    @patch("adw.integrations.telegram.TelegramClient.send_message")
    @patch("adw.integrations.telegram.TelegramConfig.load")
    def test_notify_task_started_success(
        self, mock_load: MagicMock, mock_send: MagicMock
    ) -> None:
        """Test successful task started notification."""
        from adw.integrations.telegram import notify_task_started

        mock_load.return_value = TelegramConfig(
            bot_token="123:ABC",
            chat_id="999888",
        )
        mock_send.return_value = {"message_id": 100}

        result = notify_task_started("abc123", "Test task", workflow="sdlc", model="opus")

        assert result is True
        mock_send.assert_called_once()

    @patch("adw.integrations.telegram.TelegramClient.send_message")
    @patch("adw.integrations.telegram.TelegramConfig.load")
    @patch("adw.integrations.telegram.update_task_state")
    def test_notify_task_completed_success(
        self,
        mock_update: MagicMock,
        mock_load: MagicMock,
        mock_send: MagicMock,
    ) -> None:
        """Test successful task completed notification."""
        from adw.integrations.telegram import notify_task_completed

        mock_load.return_value = TelegramConfig(
            bot_token="123:ABC",
            chat_id="999888",
        )
        mock_send.return_value = {"message_id": 100}

        result = notify_task_completed(
            "abc123",
            description="Test task",
            duration="5m",
            pr_url="https://github.com/test/pr/1",
        )

        assert result is True
        mock_update.assert_called_with("abc123", status="completed")


# =============================================================================
# Callback Query Handler Tests
# =============================================================================


class TestCallbackQueryHandlers:
    """Tests for callback query handling."""

    def test_handle_callback_query_invalid_data(self) -> None:
        """Test handling callback with invalid data."""
        client = MagicMock(spec=TelegramClient)
        callback_query = {
            "id": "query123",
            "data": "",  # Empty data
            "message": {"chat": {"id": 123}},
        }

        handle_callback_query(client, callback_query)

        client.answer_callback_query.assert_called_with("query123", "Invalid callback data")

    def test_handle_callback_query_no_underscore(self) -> None:
        """Test handling callback with no underscore in data."""
        client = MagicMock(spec=TelegramClient)
        callback_query = {
            "id": "query123",
            "data": "invalid",  # No underscore
            "message": {"chat": {"id": 123}},
        }

        handle_callback_query(client, callback_query)

        client.answer_callback_query.assert_called_with("query123", "Invalid callback format")

    def test_handle_callback_query_unknown_action(self) -> None:
        """Test handling callback with unknown action."""
        client = MagicMock(spec=TelegramClient)
        callback_query = {
            "id": "query123",
            "data": "unknown_abc123",
            "message": {"chat": {"id": 123}},
        }

        handle_callback_query(client, callback_query)

        client.answer_callback_query.assert_called()
        assert "Unknown action" in str(client.answer_callback_query.call_args)
