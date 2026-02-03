"""Tests for the unified configuration system."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from adw.config import (
    ADWConfig,
    CoreConfig,
    DaemonConfig,
    GitHubSettings,
    LinearSettings,
    NotionSettings,
    PluginSettings,
    SlackSettings,
    UIConfig,
    WebhookSettings,
    WorkflowConfig,
    WorkspaceSettings,
    _toml_value,
    _write_simple_toml,
    format_config_for_display,
    get_config,
    get_config_path,
    list_config_keys,
    load_config,
    reload_config,
    reset_config,
    save_config,
)


# =============================================================================
# CoreConfig Tests
# =============================================================================


class TestCoreConfig:
    """Tests for CoreConfig dataclass."""

    def test_defaults(self):
        """Test default values."""
        config = CoreConfig()
        assert config.tasks_file == "tasks.md"
        assert config.default_workflow == "sdlc"
        assert config.default_model == "sonnet"
        assert config.project_root == ""
        assert config.auto_detect_type is True

    def test_from_dict(self):
        """Test creating from dictionary."""
        data = {
            "tasks_file": "custom_tasks.md",
            "default_workflow": "simple",
            "default_model": "opus",
        }
        config = CoreConfig.from_dict(data)
        assert config.tasks_file == "custom_tasks.md"
        assert config.default_workflow == "simple"
        assert config.default_model == "opus"

    def test_to_dict(self):
        """Test converting to dictionary."""
        config = CoreConfig(default_model="opus")
        data = config.to_dict()
        assert data["default_model"] == "opus"
        assert "tasks_file" in data


# =============================================================================
# DaemonConfig Tests
# =============================================================================


class TestDaemonConfig:
    """Tests for DaemonConfig dataclass."""

    def test_defaults(self):
        """Test default values."""
        config = DaemonConfig()
        assert config.poll_interval == 5.0
        assert config.max_concurrent == 3
        assert config.auto_start is True
        assert config.notifications is True
        assert config.webhooks is True

    def test_from_dict(self):
        """Test creating from dictionary."""
        data = {
            "poll_interval": 10.0,
            "max_concurrent": 5,
            "auto_start": False,
        }
        config = DaemonConfig.from_dict(data)
        assert config.poll_interval == 10.0
        assert config.max_concurrent == 5
        assert config.auto_start is False

    def test_to_dict(self):
        """Test converting to dictionary."""
        config = DaemonConfig(max_concurrent=10)
        data = config.to_dict()
        assert data["max_concurrent"] == 10


# =============================================================================
# UIConfig Tests
# =============================================================================


class TestUIConfig:
    """Tests for UIConfig dataclass."""

    def test_defaults(self):
        """Test default values."""
        config = UIConfig()
        assert config.show_logo is True
        assert config.theme == "auto"
        assert config.log_level == "info"

    def test_from_dict(self):
        """Test creating from dictionary."""
        data = {
            "show_logo": False,
            "theme": "dark",
            "log_level": "debug",
        }
        config = UIConfig.from_dict(data)
        assert config.show_logo is False
        assert config.theme == "dark"
        assert config.log_level == "debug"


# =============================================================================
# WorkflowConfig Tests
# =============================================================================


class TestWorkflowConfig:
    """Tests for WorkflowConfig dataclass."""

    def test_defaults(self):
        """Test default values."""
        config = WorkflowConfig()
        assert config.default_timeout == 600
        assert config.default_retries == 2
        assert config.test_timeout == 300
        assert config.enable_checkpoints is True
        assert config.enable_wip_commits is True

    def test_from_dict(self):
        """Test creating from dictionary."""
        data = {
            "default_timeout": 1200,
            "default_retries": 5,
        }
        config = WorkflowConfig.from_dict(data)
        assert config.default_timeout == 1200
        assert config.default_retries == 5


# =============================================================================
# WorkspaceSettings Tests
# =============================================================================


class TestWorkspaceSettings:
    """Tests for WorkspaceSettings dataclass."""

    def test_defaults(self):
        """Test default values."""
        config = WorkspaceSettings()
        assert config.enable_worktrees is True
        assert config.default_branch == "main"
        assert config.auto_cleanup is True
        assert config.active_workspace == "default"

    def test_from_dict(self):
        """Test creating from dictionary."""
        data = {
            "enable_worktrees": False,
            "default_branch": "develop",
            "active_workspace": "my-workspace",
        }
        config = WorkspaceSettings.from_dict(data)
        assert config.enable_worktrees is False
        assert config.default_branch == "develop"
        assert config.active_workspace == "my-workspace"


# =============================================================================
# SlackSettings Tests
# =============================================================================


class TestSlackSettings:
    """Tests for SlackSettings dataclass."""

    def test_defaults(self):
        """Test default values."""
        config = SlackSettings()
        assert config.bot_token == ""
        assert config.signing_secret == ""
        assert config.is_configured is False

    def test_is_configured(self):
        """Test is_configured property."""
        config = SlackSettings(bot_token="xoxb-123", signing_secret="secret")
        assert config.is_configured is True

    def test_from_env(self):
        """Test creating from environment variables."""
        with patch.dict(os.environ, {
            "SLACK_BOT_TOKEN": "xoxb-test",
            "SLACK_SIGNING_SECRET": "test-secret",
            "SLACK_CHANNEL_ID": "C123",
        }):
            config = SlackSettings.from_env()
            assert config.bot_token == "xoxb-test"
            assert config.signing_secret == "test-secret"
            assert config.channel_id == "C123"

    def test_to_dict_excludes_secrets(self):
        """Test that to_dict excludes sensitive values."""
        config = SlackSettings(
            bot_token="xoxb-secret",
            signing_secret="secret",
            channel_id="C123",
        )
        data = config.to_dict()
        assert "bot_token" not in data
        assert "signing_secret" not in data
        assert data["channel_id"] == "C123"


# =============================================================================
# LinearSettings Tests
# =============================================================================


class TestLinearSettings:
    """Tests for LinearSettings dataclass."""

    def test_defaults(self):
        """Test default values."""
        config = LinearSettings()
        assert config.api_key == ""
        assert config.poll_interval == 60
        assert config.is_configured is False

    def test_is_configured(self):
        """Test is_configured property."""
        config = LinearSettings(api_key="lin_api_123")
        assert config.is_configured is True

    def test_from_env(self):
        """Test creating from environment variables."""
        with patch.dict(os.environ, {
            "LINEAR_API_KEY": "lin_api_test",
            "LINEAR_TEAM_ID": "team123",
            "LINEAR_POLL_INTERVAL": "120",
        }):
            config = LinearSettings.from_env()
            assert config.api_key == "lin_api_test"
            assert config.team_id == "team123"
            assert config.poll_interval == 120


# =============================================================================
# NotionSettings Tests
# =============================================================================


class TestNotionSettings:
    """Tests for NotionSettings dataclass."""

    def test_defaults(self):
        """Test default values."""
        config = NotionSettings()
        assert config.api_key == ""
        assert config.database_id == ""
        assert config.is_configured is False

    def test_is_configured(self):
        """Test is_configured property."""
        config = NotionSettings(api_key="secret_123", database_id="db123")
        assert config.is_configured is True

    def test_from_env(self):
        """Test creating from environment variables."""
        with patch.dict(os.environ, {
            "NOTION_API_KEY": "secret_test",
            "NOTION_DATABASE_ID": "db_test",
            "NOTION_POLL_INTERVAL": "90",
        }):
            config = NotionSettings.from_env()
            assert config.api_key == "secret_test"
            assert config.database_id == "db_test"
            assert config.poll_interval == 90


# =============================================================================
# GitHubSettings Tests
# =============================================================================


class TestGitHubSettings:
    """Tests for GitHubSettings dataclass."""

    def test_defaults(self):
        """Test default values."""
        config = GitHubSettings()
        assert config.token == ""
        assert config.poll_interval == 300
        # GitHub is always configured (uses gh CLI)
        assert config.is_configured is True

    def test_from_env(self):
        """Test creating from environment variables."""
        with patch.dict(os.environ, {
            "GITHUB_TOKEN": "ghp_test",
            "GITHUB_OWNER": "test-owner",
            "GITHUB_REPO": "test-repo",
        }, clear=False):
            config = GitHubSettings.from_env()
            assert config.token == "ghp_test"
            assert config.owner == "test-owner"
            assert config.repo == "test-repo"


# =============================================================================
# WebhookSettings Tests
# =============================================================================


class TestWebhookSettings:
    """Tests for WebhookSettings dataclass."""

    def test_defaults(self):
        """Test default values."""
        config = WebhookSettings()
        assert config.url == ""
        assert config.is_configured is False
        assert "task_completed" in config.events

    def test_is_configured(self):
        """Test is_configured property."""
        config = WebhookSettings(url="https://example.com/webhook")
        assert config.is_configured is True

    def test_from_env(self):
        """Test creating from environment variables."""
        with patch.dict(os.environ, {
            "ADW_WEBHOOK_URL": "https://test.com/hook",
            "ADW_WEBHOOK_EVENTS": "task_started,task_failed",
            "ADW_WEBHOOK_SECRET": "secret123",
        }):
            config = WebhookSettings.from_env()
            assert config.url == "https://test.com/hook"
            assert config.events == ["task_started", "task_failed"]
            assert config.secret == "secret123"


# =============================================================================
# PluginSettings Tests
# =============================================================================


class TestPluginSettings:
    """Tests for PluginSettings dataclass."""

    def test_defaults(self):
        """Test default values."""
        config = PluginSettings()
        assert config.settings == {}

    def test_get_and_set(self):
        """Test getting and setting plugin config."""
        config = PluginSettings()
        config.set("qmd", {"enabled": True, "path": "/usr/bin/qmd"})
        assert config.get("qmd") == {"enabled": True, "path": "/usr/bin/qmd"}
        assert config.get("unknown") == {}

    def test_from_dict(self):
        """Test creating from dictionary."""
        data = {"qmd": {"enabled": True}}
        config = PluginSettings.from_dict(data)
        assert config.get("qmd") == {"enabled": True}


# =============================================================================
# ADWConfig Tests
# =============================================================================


class TestADWConfig:
    """Tests for the main ADWConfig class."""

    def test_defaults(self):
        """Test default values for all sections."""
        config = ADWConfig()
        assert config.core.default_model == "sonnet"
        assert config.daemon.max_concurrent == 3
        assert config.ui.show_logo is True
        assert config.config_version == "1.0"

    def test_from_dict(self):
        """Test creating full config from dictionary."""
        data = {
            "config": {"version": "2.0"},
            "core": {"default_model": "opus"},
            "daemon": {"max_concurrent": 5},
            "ui": {"show_logo": False},
        }
        config = ADWConfig.from_dict(data)
        assert config.config_version == "2.0"
        assert config.core.default_model == "opus"
        assert config.daemon.max_concurrent == 5
        assert config.ui.show_logo is False

    def test_to_dict(self):
        """Test converting to dictionary."""
        config = ADWConfig()
        config.core.default_model = "opus"
        data = config.to_dict()
        assert data["core"]["default_model"] == "opus"
        assert "config" in data

    def test_to_dict_includes_secrets(self):
        """Test that include_secrets flag works."""
        config = ADWConfig()
        config.slack.bot_token = "xoxb-secret"

        # Without secrets
        data = config.to_dict(include_secrets=False)
        assert "bot_token" not in data.get("slack", {})

        # With secrets
        data = config.to_dict(include_secrets=True)
        assert data["slack"]["bot_token"] == "xoxb-secret"

    def test_get(self):
        """Test getting values by dotted path."""
        config = ADWConfig()
        config.core.default_model = "opus"
        config.daemon.max_concurrent = 10

        assert config.get("core.default_model") == "opus"
        assert config.get("daemon.max_concurrent") == 10
        assert config.get("unknown.key") is None
        assert config.get("unknown.key", "default") == "default"

    def test_set(self):
        """Test setting values by dotted path."""
        config = ADWConfig()

        assert config.set("core.default_model", "opus")
        assert config.core.default_model == "opus"

        assert config.set("daemon.max_concurrent", 10)
        assert config.daemon.max_concurrent == 10

        # Invalid key
        assert config.set("unknown.key", "value") is False
        assert config.set("single_key", "value") is False

    def test_apply_env_overrides(self):
        """Test that environment overrides are applied."""
        config = ADWConfig()

        with patch.dict(os.environ, {
            "SLACK_BOT_TOKEN": "env-token",
            "LINEAR_API_KEY": "env-linear",
        }):
            config.apply_env_overrides()
            assert config.slack.bot_token == "env-token"
            assert config.linear.api_key == "env-linear"


# =============================================================================
# Load/Save Tests
# =============================================================================


class TestLoadSave:
    """Tests for loading and saving configuration."""

    def test_get_config_path_default(self):
        """Test default config path."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove ADW_CONFIG if present
            os.environ.pop("ADW_CONFIG", None)
            path = get_config_path()
            assert path.name == "config.toml"
            assert ".adw" in str(path)

    def test_get_config_path_custom(self):
        """Test custom config path from environment."""
        with patch.dict(os.environ, {"ADW_CONFIG": "/custom/path/config.toml"}):
            path = get_config_path()
            assert str(path) == "/custom/path/config.toml"

    def test_load_config_nonexistent(self):
        """Test loading config when file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config = load_config(config_path)
            # Should return defaults
            assert config.core.default_model == "sonnet"
            assert config.config_path == config_path

    def test_save_and_load_config(self):
        """Test saving and loading configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"

            # Create and save config
            config = ADWConfig()
            config.core.default_model = "opus"
            config.daemon.max_concurrent = 10

            assert save_config(config, config_path)
            assert config_path.exists()

            # Load it back
            loaded = load_config(config_path)
            assert loaded.core.default_model == "opus"
            assert loaded.daemon.max_concurrent == 10

    def test_load_config_with_env_overrides(self):
        """Test that environment overrides are applied when loading."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"

            # Save config with one value
            config = ADWConfig()
            config.slack.bot_token = "file-token"
            save_config(config, config_path)

            # Load with env override
            with patch.dict(os.environ, {"SLACK_BOT_TOKEN": "env-token"}):
                loaded = load_config(config_path)
                # Env should override file
                assert loaded.slack.bot_token == "env-token"


# =============================================================================
# Singleton Tests
# =============================================================================


class TestSingleton:
    """Tests for singleton behavior."""

    def test_get_config_returns_same_instance(self):
        """Test that get_config returns singleton."""
        reset_config()
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2

    def test_reload_config_creates_new_instance(self):
        """Test that reload_config creates new instance."""
        reset_config()
        config1 = get_config()
        config2 = reload_config()
        # After reload, singleton should be updated
        assert config2 is not config1
        config3 = get_config()
        assert config3 is config2

    def test_reset_config(self):
        """Test resetting singleton."""
        reset_config()
        config1 = get_config()
        reset_config()
        config2 = get_config()
        assert config1 is not config2


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_toml_value_string(self):
        """Test TOML string formatting."""
        assert _toml_value("hello") == '"hello"'
        assert _toml_value('hello "world"') == '"hello \\"world\\""'

    def test_toml_value_bool(self):
        """Test TOML boolean formatting."""
        assert _toml_value(True) == "true"
        assert _toml_value(False) == "false"

    def test_toml_value_number(self):
        """Test TOML number formatting."""
        assert _toml_value(42) == "42"
        assert _toml_value(3.14) == "3.14"

    def test_toml_value_list(self):
        """Test TOML list formatting."""
        assert _toml_value(["a", "b"]) == '["a", "b"]'
        assert _toml_value([1, 2, 3]) == "[1, 2, 3]"

    def test_toml_value_none(self):
        """Test TOML None formatting."""
        assert _toml_value(None) == '""'

    def test_list_config_keys(self):
        """Test listing all config keys."""
        keys = list_config_keys()
        assert "core.default_model" in keys
        assert "daemon.max_concurrent" in keys
        assert "slack.bot_token" in keys
        assert len(keys) > 20  # Should have many keys

    def test_format_config_for_display(self):
        """Test formatting config for CLI display."""
        config = ADWConfig()
        config.core.default_model = "opus"

        output = format_config_for_display(config)
        assert "ADW Configuration" in output
        assert "[core]" in output
        assert "default_model = opus" in output

    def test_format_config_hides_secrets(self):
        """Test that secrets are hidden by default."""
        config = ADWConfig()
        config.slack.bot_token = "xoxb-secret-token"
        config.slack.signing_secret = "secret"

        output = format_config_for_display(config, show_secrets=False)
        assert "xoxb-secret-token" not in output

    def test_write_simple_toml(self):
        """Test simple TOML writer fallback."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ADWConfig()
            config.core.default_model = "opus"
            path = Path(tmpdir) / "test.toml"

            assert _write_simple_toml(config, path)
            assert path.exists()

            content = path.read_text()
            assert "[core]" in content
            assert 'default_model = "opus"' in content


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for full config workflow."""

    def test_full_workflow(self):
        """Test complete config workflow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"

            # Create fresh config
            config = ADWConfig()
            config.config_path = config_path

            # Modify settings
            config.core.default_model = "opus"
            config.daemon.max_concurrent = 5
            config.ui.show_logo = False
            config.slack.bot_token = "xoxb-test"
            config.plugins.set("qmd", {"enabled": True})

            # Save
            assert save_config(config, config_path)

            # Load
            loaded = load_config(config_path)

            # Verify
            assert loaded.core.default_model == "opus"
            assert loaded.daemon.max_concurrent == 5
            assert loaded.ui.show_logo is False
            assert loaded.slack.bot_token == "xoxb-test"
            assert loaded.plugins.get("qmd") == {"enabled": True}

    def test_config_with_all_integrations(self):
        """Test config with all integrations configured."""
        config = ADWConfig()

        # Configure all integrations
        config.slack.bot_token = "xoxb-test"
        config.slack.signing_secret = "secret"
        config.linear.api_key = "lin_api_test"
        config.notion.api_key = "secret_test"
        config.notion.database_id = "db_test"
        config.github.token = "ghp_test"
        config.webhook.url = "https://test.com/hook"

        # All should be configured
        assert config.slack.is_configured
        assert config.linear.is_configured
        assert config.notion.is_configured
        assert config.github.is_configured
        assert config.webhook.is_configured

        # Test round-trip
        data = config.to_dict(include_secrets=True)
        loaded = ADWConfig.from_dict(data)

        assert loaded.slack.bot_token == "xoxb-test"
        assert loaded.linear.api_key == "lin_api_test"
