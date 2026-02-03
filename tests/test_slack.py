"""Tests for Slack integration.

Tests cover:
- SlackConfig creation and loading
- SlackClient request building (mocked)
- Request signature verification
- Slash command parsing and handling
- Interaction payload parsing
- Message formatting
- State management
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from adw.integrations.slack import (
    InteractionPayload,
    SlackClient,
    SlackConfig,
    SlashCommandRequest,
    _handle_help_command,
    _load_slack_state,
    _parse_simple_toml,
    _save_slack_state,
    _save_slack_task_state,
    _update_slack_task_state,
    format_approval_request_message,
    format_status_message,
    format_task_completed_message,
    format_task_failed_message,
    format_task_started_message,
    handle_slash_command,
    verify_slack_request,
)

# =============================================================================
# SlackConfig Tests
# =============================================================================


class TestSlackConfig:
    """Tests for SlackConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default config values."""
        config = SlackConfig(
            bot_token="xoxb-test",
            signing_secret="secret123",
        )

        assert config.bot_token == "xoxb-test"
        assert config.signing_secret == "secret123"
        assert config.channel_id is None
        assert config.notification_events == ["task_started", "task_completed", "task_failed"]

    def test_custom_values(self) -> None:
        """Test config with custom values."""
        config = SlackConfig(
            bot_token="xoxb-custom",
            signing_secret="custom_secret",
            channel_id="C12345678",
            notification_events=["task_completed"],
        )

        assert config.bot_token == "xoxb-custom"
        assert config.signing_secret == "custom_secret"
        assert config.channel_id == "C12345678"
        assert config.notification_events == ["task_completed"]

    def test_from_env(self) -> None:
        """Test loading config from environment."""
        with patch.dict(
            os.environ,
            {
                "SLACK_BOT_TOKEN": "xoxb-env",
                "SLACK_SIGNING_SECRET": "env_secret",
                "SLACK_CHANNEL_ID": "C99999999",
            },
        ):
            config = SlackConfig.from_env()
            assert config is not None
            assert config.bot_token == "xoxb-env"
            assert config.signing_secret == "env_secret"
            assert config.channel_id == "C99999999"

    def test_from_env_missing_required(self) -> None:
        """Test from_env returns None when required vars missing."""
        with patch.dict(os.environ, {}, clear=True):
            config = SlackConfig.from_env()
            assert config is None

    def test_from_env_partial(self) -> None:
        """Test from_env returns None with partial config."""
        with patch.dict(os.environ, {"SLACK_BOT_TOKEN": "xoxb-test"}, clear=True):
            config = SlackConfig.from_env()
            assert config is None

    def test_from_config_file(self) -> None:
        """Test loading config from TOML file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("[slack]\n")
            f.write('bot_token = "xoxb-file"\n')
            f.write('signing_secret = "file_secret"\n')
            f.write('channel_id = "C11111111"\n')
            f.flush()

            config = SlackConfig.from_config_file(Path(f.name))

            assert config is not None
            assert config.bot_token == "xoxb-file"
            assert config.signing_secret == "file_secret"
            assert config.channel_id == "C11111111"

            os.unlink(f.name)

    def test_from_config_file_missing(self) -> None:
        """Test from_config_file returns None for missing file."""
        config = SlackConfig.from_config_file(Path("/nonexistent/config.toml"))
        assert config is None

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        config = SlackConfig(
            bot_token="xoxb-test",
            signing_secret="secret",
            channel_id="C12345678",
        )

        result = config.to_dict()
        assert result["channel_id"] == "C12345678"
        assert "notification_events" in result
        # Note: bot_token and signing_secret not included for security


# =============================================================================
# Request Verification Tests
# =============================================================================


class TestRequestVerification:
    """Tests for Slack request signature verification."""

    def test_valid_signature(self) -> None:
        """Test verification of valid signature."""
        signing_secret = "test_secret"
        timestamp = str(int(time.time()))
        body = b"test=payload"

        sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
        expected_sig = (
            "v0="
            + hmac.new(
                signing_secret.encode(),
                sig_basestring.encode(),
                hashlib.sha256,
            ).hexdigest()
        )

        result = verify_slack_request(signing_secret, timestamp, expected_sig, body)
        assert result is True

    def test_invalid_signature(self) -> None:
        """Test rejection of invalid signature."""
        result = verify_slack_request(
            "secret",
            str(int(time.time())),
            "v0=invalid",
            b"body",
        )
        assert result is False

    def test_expired_timestamp(self) -> None:
        """Test rejection of old timestamps (>5 minutes)."""
        signing_secret = "test_secret"
        old_timestamp = str(int(time.time()) - 400)  # 6+ minutes old
        body = b"test=payload"

        sig_basestring = f"v0:{old_timestamp}:{body.decode('utf-8')}"
        signature = (
            "v0="
            + hmac.new(
                signing_secret.encode(),
                sig_basestring.encode(),
                hashlib.sha256,
            ).hexdigest()
        )

        result = verify_slack_request(signing_secret, old_timestamp, signature, body)
        assert result is False

    def test_invalid_timestamp(self) -> None:
        """Test rejection of non-numeric timestamp."""
        result = verify_slack_request("secret", "not_a_number", "v0=sig", b"body")
        assert result is False


# =============================================================================
# SlashCommandRequest Tests
# =============================================================================


class TestSlashCommandRequest:
    """Tests for SlashCommandRequest parsing."""

    def test_from_form_data(self) -> None:
        """Test parsing from Slack form data."""
        data = {
            "command": "/adw",
            "text": "create Fix the login bug",
            "user_id": "U12345678",
            "user_name": "testuser",
            "channel_id": "C12345678",
            "channel_name": "general",
            "team_id": "T12345678",
            "response_url": "https://hooks.slack.com/response",
            "trigger_id": "123.456.789",
        }

        request = SlashCommandRequest.from_form_data(data)

        assert request.command == "/adw"
        assert request.text == "create Fix the login bug"
        assert request.user_id == "U12345678"
        assert request.channel_id == "C12345678"
        assert request.trigger_id == "123.456.789"

    def test_from_form_data_empty(self) -> None:
        """Test parsing with empty data."""
        request = SlashCommandRequest.from_form_data({})

        assert request.command == ""
        assert request.text == ""
        assert request.user_id == ""

    def test_get_subcommand(self) -> None:
        """Test parsing subcommand from text."""
        data = {"text": "create Fix the bug", "command": "/adw"}
        request = SlashCommandRequest.from_form_data(data)

        subcommand, args = request.get_subcommand()
        assert subcommand == "create"
        assert args == "Fix the bug"

    def test_get_subcommand_no_args(self) -> None:
        """Test parsing subcommand with no args."""
        data = {"text": "status", "command": "/adw"}
        request = SlashCommandRequest.from_form_data(data)

        subcommand, args = request.get_subcommand()
        assert subcommand == "status"
        assert args == ""

    def test_get_subcommand_empty(self) -> None:
        """Test parsing empty text defaults to help."""
        data = {"text": "", "command": "/adw"}
        request = SlashCommandRequest.from_form_data(data)

        subcommand, args = request.get_subcommand()
        assert subcommand == "help"
        assert args == ""

    def test_get_subcommand_case_insensitive(self) -> None:
        """Test subcommand parsing is case insensitive."""
        data = {"text": "CREATE Something", "command": "/adw"}
        request = SlashCommandRequest.from_form_data(data)

        subcommand, args = request.get_subcommand()
        assert subcommand == "create"
        assert args == "Something"


# =============================================================================
# InteractionPayload Tests
# =============================================================================


class TestInteractionPayload:
    """Tests for InteractionPayload parsing."""

    def test_from_dict(self) -> None:
        """Test parsing from interaction payload."""
        data = {
            "type": "block_actions",
            "user": {"id": "U12345678", "name": "testuser"},
            "channel": {"id": "C12345678"},
            "actions": [{"action_id": "approve_task_abc123", "value": "abc123"}],
            "trigger_id": "123.456.789",
            "response_url": "https://hooks.slack.com/response",
            "message": {"ts": "1234567890.123456"},
        }

        payload = InteractionPayload.from_dict(data)

        assert payload.type == "block_actions"
        assert payload.user_id == "U12345678"
        assert payload.user_name == "testuser"
        assert payload.channel_id == "C12345678"
        assert payload.action_id == "approve_task_abc123"
        assert payload.action_value == "abc123"
        assert payload.message_ts == "1234567890.123456"

    def test_from_dict_minimal(self) -> None:
        """Test parsing with minimal data."""
        payload = InteractionPayload.from_dict({})

        assert payload.type == ""
        assert payload.user_id == ""
        assert payload.channel_id is None
        assert payload.action_id == ""


# =============================================================================
# Message Formatting Tests
# =============================================================================


class TestMessageFormatting:
    """Tests for Slack message formatting functions."""

    def test_format_task_started_message(self) -> None:
        """Test task started message formatting."""
        message = format_task_started_message(
            adw_id="abc12345",
            description="Fix the login bug",
            workflow="standard",
            user_id="U12345678",
        )

        assert "text" in message
        assert "blocks" in message
        assert "Task Started" in message["blocks"][0]["text"]["text"]
        assert "<@U12345678>" in message["blocks"][0]["text"]["text"]
        assert "abc12345" in str(message["blocks"])

    def test_format_task_started_no_user(self) -> None:
        """Test task started message without user mention."""
        message = format_task_started_message(
            adw_id="abc12345",
            description="Fix the bug",
            workflow="sdlc",
        )

        assert "text" in message
        assert "<@" not in message["blocks"][0]["text"]["text"]

    def test_format_task_completed_message(self) -> None:
        """Test task completed message formatting."""
        message = format_task_completed_message(
            adw_id="abc12345",
            description="Fix completed",
            duration_seconds=125,
            pr_url="https://github.com/org/repo/pull/123",
        )

        assert "Completed" in message["blocks"][0]["text"]["text"]
        assert "2m 5s" in message["blocks"][0]["text"]["text"]
        assert "View Pull Request" in message["blocks"][0]["text"]["text"]

    def test_format_task_completed_no_extras(self) -> None:
        """Test completed message without duration or PR."""
        message = format_task_completed_message(
            adw_id="abc12345",
            description="Task done",
        )

        assert "Completed" in message["blocks"][0]["text"]["text"]
        assert "Pull Request" not in message["blocks"][0]["text"]["text"]

    def test_format_task_failed_message(self) -> None:
        """Test task failed message formatting."""
        message = format_task_failed_message(
            adw_id="abc12345",
            description="Task failed",
            error="Tests did not pass",
        )

        assert "Failed" in message["blocks"][0]["text"]["text"]
        assert "Tests did not pass" in message["blocks"][0]["text"]["text"]
        # Should have action buttons
        assert any(b.get("type") == "actions" for b in message["blocks"])

    def test_format_task_failed_no_error(self) -> None:
        """Test failed message without error details."""
        message = format_task_failed_message(
            adw_id="abc12345",
            description="Failed",
        )

        assert "Failed" in message["blocks"][0]["text"]["text"]

    def test_format_approval_request_message(self) -> None:
        """Test approval request message formatting."""
        message = format_approval_request_message(
            adw_id="abc12345",
            description="Implement feature X",
            plan_summary="1. Do this\n2. Do that",
        )

        assert "Approval Required" in message["blocks"][0]["text"]["text"]
        assert "Plan Summary" in message["blocks"][0]["text"]["text"]
        # Should have approve/reject buttons
        actions = [b for b in message["blocks"] if b.get("type") == "actions"]
        assert len(actions) == 1
        assert len(actions[0]["elements"]) == 3  # Approve, Reject, View Details

    def test_format_status_message_with_tasks(self) -> None:
        """Test status message with tasks."""
        tasks = [
            {"adw_id": "abc123", "description": "Task 1", "status": "in_progress"},
            {"adw_id": "def456", "description": "Task 2", "status": "completed"},
            {"adw_id": "ghi789", "description": "Task 3", "status": "failed"},
        ]

        message = format_status_message(tasks)

        assert "Status" in message["blocks"][0]["text"]["text"]
        assert "abc123" in message["blocks"][0]["text"]["text"]
        assert "def456" in message["blocks"][0]["text"]["text"]

    def test_format_status_message_empty(self) -> None:
        """Test status message with no tasks."""
        message = format_status_message([])

        assert "No active tasks" in message["blocks"][0]["text"]["text"]


# =============================================================================
# Slash Command Handler Tests
# =============================================================================


class TestSlashCommandHandler:
    """Tests for slash command handling."""

    def test_handle_help_command(self) -> None:
        """Test help command returns usage info."""
        response = _handle_help_command()

        assert response["response_type"] == "ephemeral"
        assert "ADW Slack Commands" in response["blocks"][0]["text"]["text"]
        assert "/adw create" in response["blocks"][0]["text"]["text"]
        assert "/adw status" in response["blocks"][0]["text"]["text"]
        assert "/adw approve" in response["blocks"][0]["text"]["text"]

    def test_handle_unknown_command(self) -> None:
        """Test unknown command returns error."""
        config = SlackConfig(bot_token="test", signing_secret="test")
        request = SlashCommandRequest.from_form_data(
            {"text": "unknown_cmd", "command": "/adw"}
        )

        response = handle_slash_command(request, config)

        assert response["response_type"] == "ephemeral"
        assert "Unknown command" in response["text"]


# =============================================================================
# State Management Tests
# =============================================================================


class TestStateManagement:
    """Tests for Slack state persistence."""

    def test_save_and_load_state(self) -> None:
        """Test saving and loading state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("adw.integrations.slack.ADW_DIR", Path(tmpdir)):
                with patch(
                    "adw.integrations.slack.SLACK_STATE_FILE",
                    Path(tmpdir) / "slack_state.json",
                ):
                    # Save state
                    state = {"tasks": {"abc123": {"description": "Test"}}}
                    _save_slack_state(state)

                    # Load state
                    loaded = _load_slack_state()
                    assert loaded == state

    def test_load_missing_state(self) -> None:
        """Test loading from nonexistent file returns empty state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch(
                "adw.integrations.slack.SLACK_STATE_FILE",
                Path(tmpdir) / "nonexistent.json",
            ):
                state = _load_slack_state()
                assert state == {"tasks": {}}

    def test_save_task_state(self) -> None:
        """Test saving task state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("adw.integrations.slack.ADW_DIR", Path(tmpdir)):
                with patch(
                    "adw.integrations.slack.SLACK_STATE_FILE",
                    Path(tmpdir) / "slack_state.json",
                ):
                    _save_slack_task_state(
                        adw_id="abc123",
                        channel_id="C12345678",
                        user_id="U12345678",
                        description="Test task",
                        thread_ts="1234567890.123456",
                    )

                    state = _load_slack_state()
                    assert "abc123" in state["tasks"]
                    assert state["tasks"]["abc123"]["channel_id"] == "C12345678"
                    assert state["tasks"]["abc123"]["thread_ts"] == "1234567890.123456"

    def test_update_task_state(self) -> None:
        """Test updating task state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("adw.integrations.slack.ADW_DIR", Path(tmpdir)):
                with patch(
                    "adw.integrations.slack.SLACK_STATE_FILE",
                    Path(tmpdir) / "slack_state.json",
                ):
                    # First save
                    _save_slack_task_state(
                        adw_id="abc123",
                        channel_id="C12345678",
                        user_id="U12345678",
                        description="Test",
                    )

                    # Update
                    _update_slack_task_state("abc123", thread_ts="updated.ts")

                    state = _load_slack_state()
                    assert state["tasks"]["abc123"]["thread_ts"] == "updated.ts"


# =============================================================================
# SlackClient Tests (Mocked)
# =============================================================================


class TestSlackClient:
    """Tests for SlackClient API calls (mocked)."""

    def test_post_message_success(self) -> None:
        """Test successful message posting."""
        client = SlackClient("xoxb-test")

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {"ok": True, "ts": "1234567890.123456"}
        ).encode()
        mock_response.status = 200
        mock_response.headers = {}
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = client.post_message(channel="C12345678", text="Hello")

        assert result is not None
        assert result["ts"] == "1234567890.123456"

    def test_post_message_with_blocks(self) -> None:
        """Test posting message with blocks."""
        client = SlackClient("xoxb-test")

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"ok": True, "ts": "123"}).encode()
        mock_response.status = 200
        mock_response.headers = {}
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "Test"}}]

        with patch("urllib.request.urlopen", return_value=mock_response) as mock_open:
            result = client.post_message(
                channel="C12345678", text="Hello", blocks=blocks
            )

        assert result is not None
        # Verify request included blocks
        call_args = mock_open.call_args
        request = call_args[0][0]
        body = json.loads(request.data.decode())
        assert body["blocks"] == blocks

    def test_post_message_in_thread(self) -> None:
        """Test posting message in thread."""
        client = SlackClient("xoxb-test")

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"ok": True, "ts": "123"}).encode()
        mock_response.status = 200
        mock_response.headers = {}
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response) as mock_open:
            result = client.post_message(
                channel="C12345678",
                text="Thread reply",
                thread_ts="1234567890.123456",
            )

        assert result is not None
        # Verify thread_ts was included
        call_args = mock_open.call_args
        request = call_args[0][0]
        body = json.loads(request.data.decode())
        assert body["thread_ts"] == "1234567890.123456"

    def test_auth_test(self) -> None:
        """Test auth.test API call."""
        client = SlackClient("xoxb-test")

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {
                "ok": True,
                "user": "testbot",
                "team": "TestTeam",
                "user_id": "U12345678",
            }
        ).encode()
        mock_response.status = 200
        mock_response.headers = {}
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = client.auth_test()

        assert result is not None
        assert result["user"] == "testbot"

    def test_api_error_handling(self) -> None:
        """Test handling of Slack API errors."""
        client = SlackClient("xoxb-test")

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {"ok": False, "error": "channel_not_found"}
        ).encode()
        mock_response.status = 200
        mock_response.headers = {}
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = client.post_message(channel="C_invalid", text="Test")

        assert result is None


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_parse_simple_toml(self) -> None:
        """Test simple TOML parsing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("[slack]\n")
            f.write('bot_token = "xoxb-test"\n')
            f.write("poll_interval = 60\n")
            f.write("# comment\n")
            f.write("\n")
            f.write("[other]\n")
            f.write('key = "value"\n')
            f.flush()

            config = _parse_simple_toml(Path(f.name))

            assert config["slack"]["bot_token"] == "xoxb-test"
            assert config["slack"]["poll_interval"] == 60
            assert config["other"]["key"] == "value"

            os.unlink(f.name)
