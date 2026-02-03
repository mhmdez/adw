"""Unified configuration system for ADW.

This module provides a single, consolidated configuration system for all ADW settings.
Configuration is stored at ~/.adw/config.toml and organized into sections.

Configuration loading priority:
1. Environment variables (highest)
2. Config file (~/.adw/config.toml)
3. Defaults (lowest)

Sections:
    [core]       - Core ADW settings (tasks file, default workflow/model)
    [daemon]     - Cron daemon settings (poll interval, concurrency)
    [ui]         - TUI and notification settings
    [workflow]   - Workflow execution settings
    [workspace]  - Workspace and multi-repo settings
    [plugins]    - Plugin configuration
    [slack]      - Slack integration
    [linear]     - Linear integration
    [notion]     - Notion integration
    [github]     - GitHub integration
    [webhook]    - Generic webhook settings

Example:
    from adw.config import get_config, ADWConfig

    config = get_config()
    print(config.core.default_model)
    print(config.daemon.max_concurrent)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default config location
DEFAULT_CONFIG_DIR = Path.home() / ".adw"
DEFAULT_CONFIG_FILE = "config.toml"

# Singleton instance
_config: ADWConfig | None = None


# =============================================================================
# Configuration Sections
# =============================================================================


@dataclass
class CoreConfig:
    """Core ADW settings.

    Attributes:
        tasks_file: Path to tasks.md relative to project root.
        default_workflow: Default workflow for tasks (sdlc, simple, standard).
        default_model: Default model for tasks (sonnet, opus, haiku).
        project_root: Override project root detection.
        auto_detect_type: Automatically detect project type.
    """

    tasks_file: str = "tasks.md"
    default_workflow: str = "sdlc"
    default_model: str = "sonnet"
    project_root: str = ""
    auto_detect_type: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CoreConfig:
        """Create from dictionary."""
        return cls(
            tasks_file=data.get("tasks_file", "tasks.md"),
            default_workflow=data.get("default_workflow", "sdlc"),
            default_model=data.get("default_model", "sonnet"),
            project_root=data.get("project_root", ""),
            auto_detect_type=data.get("auto_detect_type", True),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tasks_file": self.tasks_file,
            "default_workflow": self.default_workflow,
            "default_model": self.default_model,
            "project_root": self.project_root,
            "auto_detect_type": self.auto_detect_type,
        }


@dataclass
class DaemonConfig:
    """Cron daemon settings.

    Attributes:
        poll_interval: Seconds between task checks.
        max_concurrent: Maximum simultaneous agents.
        auto_start: Automatically start tasks when eligible.
        notifications: Enable desktop notifications.
        webhooks: Enable webhook notifications.
    """

    poll_interval: float = 5.0
    max_concurrent: int = 3
    auto_start: bool = True
    notifications: bool = True
    webhooks: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DaemonConfig:
        """Create from dictionary."""
        return cls(
            poll_interval=float(data.get("poll_interval", 5.0)),
            max_concurrent=int(data.get("max_concurrent", 3)),
            auto_start=data.get("auto_start", True),
            notifications=data.get("notifications", True),
            webhooks=data.get("webhooks", True),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "poll_interval": self.poll_interval,
            "max_concurrent": self.max_concurrent,
            "auto_start": self.auto_start,
            "notifications": self.notifications,
            "webhooks": self.webhooks,
        }


@dataclass
class UIConfig:
    """UI and notification settings.

    Attributes:
        show_logo: Show ASCII logo in TUI.
        theme: Color theme (auto, dark, light).
        notification_sound_success: Sound for success notifications.
        notification_sound_failure: Sound for failure notifications.
        notification_on_start: Notify when tasks start.
        log_level: Logging level (debug, info, warning, error).
    """

    show_logo: bool = True
    theme: str = "auto"
    notification_sound_success: str = "Glass"
    notification_sound_failure: str = "Basso"
    notification_on_start: bool = False
    log_level: str = "info"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UIConfig:
        """Create from dictionary."""
        return cls(
            show_logo=data.get("show_logo", True),
            theme=data.get("theme", "auto"),
            notification_sound_success=data.get("notification_sound_success", "Glass"),
            notification_sound_failure=data.get("notification_sound_failure", "Basso"),
            notification_on_start=data.get("notification_on_start", False),
            log_level=data.get("log_level", "info"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "show_logo": self.show_logo,
            "theme": self.theme,
            "notification_sound_success": self.notification_sound_success,
            "notification_sound_failure": self.notification_sound_failure,
            "notification_on_start": self.notification_on_start,
            "log_level": self.log_level,
        }


@dataclass
class WorkflowConfig:
    """Workflow execution settings.

    Attributes:
        default_timeout: Default phase timeout in seconds.
        default_retries: Default max retries per phase.
        test_timeout: Default test execution timeout.
        enable_checkpoints: Enable checkpoint saving.
        enable_wip_commits: Create WIP commits on pause.
    """

    default_timeout: int = 600
    default_retries: int = 2
    test_timeout: int = 300
    enable_checkpoints: bool = True
    enable_wip_commits: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkflowConfig:
        """Create from dictionary."""
        return cls(
            default_timeout=int(data.get("default_timeout", 600)),
            default_retries=int(data.get("default_retries", 2)),
            test_timeout=int(data.get("test_timeout", 300)),
            enable_checkpoints=data.get("enable_checkpoints", True),
            enable_wip_commits=data.get("enable_wip_commits", True),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "default_timeout": self.default_timeout,
            "default_retries": self.default_retries,
            "test_timeout": self.test_timeout,
            "enable_checkpoints": self.enable_checkpoints,
            "enable_wip_commits": self.enable_wip_commits,
        }


@dataclass
class WorkspaceSettings:
    """Workspace and multi-repo settings.

    Attributes:
        enable_worktrees: Use git worktrees for task isolation.
        default_branch: Default git branch name.
        auto_cleanup: Automatically cleanup completed worktrees.
        active_workspace: Currently active workspace name.
    """

    enable_worktrees: bool = True
    default_branch: str = "main"
    auto_cleanup: bool = True
    active_workspace: str = "default"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkspaceSettings:
        """Create from dictionary."""
        return cls(
            enable_worktrees=data.get("enable_worktrees", True),
            default_branch=data.get("default_branch", "main"),
            auto_cleanup=data.get("auto_cleanup", True),
            active_workspace=data.get("active_workspace", "default"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "enable_worktrees": self.enable_worktrees,
            "default_branch": self.default_branch,
            "auto_cleanup": self.auto_cleanup,
            "active_workspace": self.active_workspace,
        }


@dataclass
class SlackSettings:
    """Slack integration settings.

    Attributes:
        bot_token: Slack bot token (xoxb-...).
        signing_secret: Slack signing secret for request verification.
        channel_id: Default channel for notifications.
        notification_events: Events to notify on.
    """

    bot_token: str = ""
    signing_secret: str = ""
    channel_id: str = ""
    notification_events: list[str] = field(
        default_factory=lambda: ["task_started", "task_completed", "task_failed"]
    )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SlackSettings:
        """Create from dictionary."""
        return cls(
            bot_token=data.get("bot_token", ""),
            signing_secret=data.get("signing_secret", ""),
            channel_id=data.get("channel_id", ""),
            notification_events=data.get(
                "notification_events",
                ["task_started", "task_completed", "task_failed"],
            ),
        )

    @classmethod
    def from_env(cls) -> SlackSettings:
        """Create from environment variables."""
        return cls(
            bot_token=os.environ.get("SLACK_BOT_TOKEN", ""),
            signing_secret=os.environ.get("SLACK_SIGNING_SECRET", ""),
            channel_id=os.environ.get("SLACK_CHANNEL_ID", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary (excludes secrets)."""
        return {
            "channel_id": self.channel_id,
            "notification_events": self.notification_events,
        }

    @property
    def is_configured(self) -> bool:
        """Check if Slack is properly configured."""
        return bool(self.bot_token and self.signing_secret)


@dataclass
class LinearSettings:
    """Linear integration settings.

    Attributes:
        api_key: Linear API key.
        team_id: Team ID to poll.
        poll_interval: Seconds between polls.
        filter_states: Only process issues in these states.
        sync_comments: Sync ADW updates as comments.
        label_filter: Only process issues with these labels.
    """

    api_key: str = ""
    team_id: str = ""
    poll_interval: int = 60
    filter_states: list[str] = field(
        default_factory=lambda: ["Backlog", "Todo", "Triage"]
    )
    sync_comments: bool = True
    label_filter: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LinearSettings:
        """Create from dictionary."""
        return cls(
            api_key=data.get("api_key", ""),
            team_id=data.get("team_id", ""),
            poll_interval=int(data.get("poll_interval", 60)),
            filter_states=data.get("filter_states", ["Backlog", "Todo", "Triage"]),
            sync_comments=data.get("sync_comments", True),
            label_filter=data.get("label_filter", []),
        )

    @classmethod
    def from_env(cls) -> LinearSettings:
        """Create from environment variables."""
        return cls(
            api_key=os.environ.get("LINEAR_API_KEY", ""),
            team_id=os.environ.get("LINEAR_TEAM_ID", ""),
            poll_interval=int(os.environ.get("LINEAR_POLL_INTERVAL", "60")),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary (excludes secrets)."""
        return {
            "team_id": self.team_id,
            "poll_interval": self.poll_interval,
            "filter_states": self.filter_states,
            "sync_comments": self.sync_comments,
            "label_filter": self.label_filter,
        }

    @property
    def is_configured(self) -> bool:
        """Check if Linear is properly configured."""
        return bool(self.api_key)


@dataclass
class NotionSettings:
    """Notion integration settings.

    Attributes:
        api_key: Notion integration API key.
        database_id: Database ID to poll.
        poll_interval: Seconds between polls.
        status_property: Name of status property.
        title_property: Name of title property.
        workflow_property: Name of workflow property.
        model_property: Name of model property.
        priority_property: Name of priority property.
        adw_id_property: Name of ADW ID property.
        filter_status: Only process tasks with these statuses.
    """

    api_key: str = ""
    database_id: str = ""
    poll_interval: int = 60
    status_property: str = "Status"
    title_property: str = "Name"
    workflow_property: str = "Workflow"
    model_property: str = "Model"
    priority_property: str = "Priority"
    adw_id_property: str = "ADW ID"
    filter_status: list[str] = field(default_factory=lambda: ["To Do", "Not Started"])

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NotionSettings:
        """Create from dictionary."""
        return cls(
            api_key=data.get("api_key", ""),
            database_id=data.get("database_id", ""),
            poll_interval=int(data.get("poll_interval", 60)),
            status_property=data.get("status_property", "Status"),
            title_property=data.get("title_property", "Name"),
            workflow_property=data.get("workflow_property", "Workflow"),
            model_property=data.get("model_property", "Model"),
            priority_property=data.get("priority_property", "Priority"),
            adw_id_property=data.get("adw_id_property", "ADW ID"),
            filter_status=data.get("filter_status", ["To Do", "Not Started"]),
        )

    @classmethod
    def from_env(cls) -> NotionSettings:
        """Create from environment variables."""
        return cls(
            api_key=os.environ.get("NOTION_API_KEY", ""),
            database_id=os.environ.get("NOTION_DATABASE_ID", ""),
            poll_interval=int(os.environ.get("NOTION_POLL_INTERVAL", "60")),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary (excludes secrets)."""
        return {
            "database_id": self.database_id,
            "poll_interval": self.poll_interval,
            "status_property": self.status_property,
            "title_property": self.title_property,
            "workflow_property": self.workflow_property,
            "model_property": self.model_property,
            "priority_property": self.priority_property,
            "adw_id_property": self.adw_id_property,
            "filter_status": self.filter_status,
        }

    @property
    def is_configured(self) -> bool:
        """Check if Notion is properly configured."""
        return bool(self.api_key and self.database_id)


@dataclass
class GitHubSettings:
    """GitHub integration settings.

    Attributes:
        token: GitHub personal access token (optional, uses gh CLI if not set).
        owner: Default repository owner.
        repo: Default repository name.
        poll_interval: Seconds between issue polls.
        labels: Only process issues with these labels.
    """

    token: str = ""
    owner: str = ""
    repo: str = ""
    poll_interval: int = 300
    labels: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GitHubSettings:
        """Create from dictionary."""
        return cls(
            token=data.get("token", ""),
            owner=data.get("owner", ""),
            repo=data.get("repo", ""),
            poll_interval=int(data.get("poll_interval", 300)),
            labels=data.get("labels", []),
        )

    @classmethod
    def from_env(cls) -> GitHubSettings:
        """Create from environment variables."""
        return cls(
            token=os.environ.get("GITHUB_TOKEN", os.environ.get("GH_TOKEN", "")),
            owner=os.environ.get("GITHUB_OWNER", ""),
            repo=os.environ.get("GITHUB_REPO", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary (excludes secrets)."""
        return {
            "owner": self.owner,
            "repo": self.repo,
            "poll_interval": self.poll_interval,
            "labels": self.labels,
        }

    @property
    def is_configured(self) -> bool:
        """Check if GitHub is properly configured."""
        # GitHub can work without token (uses gh CLI)
        return True


@dataclass
class WebhookSettings:
    """Generic webhook settings.

    Attributes:
        url: Webhook URL for notifications.
        events: Events to send to webhook.
        secret: Optional webhook secret for signing.
    """

    url: str = ""
    events: list[str] = field(
        default_factory=lambda: ["task_completed", "task_failed"]
    )
    secret: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WebhookSettings:
        """Create from dictionary."""
        return cls(
            url=data.get("url", ""),
            events=data.get("events", ["task_completed", "task_failed"]),
            secret=data.get("secret", ""),
        )

    @classmethod
    def from_env(cls) -> WebhookSettings:
        """Create from environment variables."""
        events_str = os.environ.get("ADW_WEBHOOK_EVENTS", "task_completed,task_failed")
        return cls(
            url=os.environ.get("ADW_WEBHOOK_URL", ""),
            events=events_str.split(",") if events_str else [],
            secret=os.environ.get("ADW_WEBHOOK_SECRET", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary (excludes secrets)."""
        return {
            "url": self.url,
            "events": self.events,
        }

    @property
    def is_configured(self) -> bool:
        """Check if webhook is properly configured."""
        return bool(self.url)


@dataclass
class PluginSettings:
    """Plugin-specific settings stored as dict."""

    settings: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PluginSettings:
        """Create from dictionary."""
        return cls(settings=data)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return self.settings

    def get(self, plugin_name: str) -> dict[str, Any]:
        """Get settings for a specific plugin."""
        return self.settings.get(plugin_name, {})

    def set(self, plugin_name: str, settings: dict[str, Any]) -> None:
        """Set settings for a specific plugin."""
        self.settings[plugin_name] = settings


# =============================================================================
# Main Configuration Class
# =============================================================================


@dataclass
class ADWConfig:
    """Main ADW configuration container.

    Contains all configuration sections for the application.
    Use get_config() to get the singleton instance.
    """

    core: CoreConfig = field(default_factory=CoreConfig)
    daemon: DaemonConfig = field(default_factory=DaemonConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    workflow: WorkflowConfig = field(default_factory=WorkflowConfig)
    workspace: WorkspaceSettings = field(default_factory=WorkspaceSettings)
    slack: SlackSettings = field(default_factory=SlackSettings)
    linear: LinearSettings = field(default_factory=LinearSettings)
    notion: NotionSettings = field(default_factory=NotionSettings)
    github: GitHubSettings = field(default_factory=GitHubSettings)
    webhook: WebhookSettings = field(default_factory=WebhookSettings)
    plugins: PluginSettings = field(default_factory=PluginSettings)

    # Metadata
    config_version: str = "1.0"
    config_path: Path | None = None
    last_modified: datetime | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ADWConfig:
        """Create configuration from dictionary."""
        return cls(
            core=CoreConfig.from_dict(data.get("core", {})),
            daemon=DaemonConfig.from_dict(data.get("daemon", {})),
            ui=UIConfig.from_dict(data.get("ui", {})),
            workflow=WorkflowConfig.from_dict(data.get("workflow", {})),
            workspace=WorkspaceSettings.from_dict(data.get("workspace", {})),
            slack=SlackSettings.from_dict(data.get("slack", {})),
            linear=LinearSettings.from_dict(data.get("linear", {})),
            notion=NotionSettings.from_dict(data.get("notion", {})),
            github=GitHubSettings.from_dict(data.get("github", {})),
            webhook=WebhookSettings.from_dict(data.get("webhook", {})),
            plugins=PluginSettings.from_dict(data.get("plugins", {})),
            config_version=data.get("config", {}).get("version", "1.0"),
        )

    def to_dict(self, include_secrets: bool = False) -> dict[str, Any]:
        """Convert configuration to dictionary.

        Args:
            include_secrets: If True, include sensitive values like API keys.

        Returns:
            Dictionary representation of configuration.
        """
        result = {
            "config": {
                "version": self.config_version,
            },
            "core": self.core.to_dict(),
            "daemon": self.daemon.to_dict(),
            "ui": self.ui.to_dict(),
            "workflow": self.workflow.to_dict(),
            "workspace": self.workspace.to_dict(),
        }

        # Add integration configs (without secrets by default)
        if include_secrets:
            result["slack"] = {
                "bot_token": self.slack.bot_token,
                "signing_secret": self.slack.signing_secret,
                **self.slack.to_dict(),
            }
            result["linear"] = {
                "api_key": self.linear.api_key,
                **self.linear.to_dict(),
            }
            result["notion"] = {
                "api_key": self.notion.api_key,
                **self.notion.to_dict(),
            }
            result["github"] = {
                "token": self.github.token,
                **self.github.to_dict(),
            }
            result["webhook"] = {
                "secret": self.webhook.secret,
                **self.webhook.to_dict(),
            }
        else:
            result["slack"] = self.slack.to_dict()
            result["linear"] = self.linear.to_dict()
            result["notion"] = self.notion.to_dict()
            result["github"] = self.github.to_dict()
            result["webhook"] = self.webhook.to_dict()

        # Add plugins
        if self.plugins.settings:
            result["plugins"] = self.plugins.to_dict()

        return result

    def apply_env_overrides(self) -> None:
        """Apply environment variable overrides to configuration."""
        # Slack
        env_slack = SlackSettings.from_env()
        if env_slack.bot_token:
            self.slack.bot_token = env_slack.bot_token
        if env_slack.signing_secret:
            self.slack.signing_secret = env_slack.signing_secret
        if env_slack.channel_id:
            self.slack.channel_id = env_slack.channel_id

        # Linear
        env_linear = LinearSettings.from_env()
        if env_linear.api_key:
            self.linear.api_key = env_linear.api_key
        if env_linear.team_id:
            self.linear.team_id = env_linear.team_id
        if os.environ.get("LINEAR_POLL_INTERVAL"):
            self.linear.poll_interval = env_linear.poll_interval

        # Notion
        env_notion = NotionSettings.from_env()
        if env_notion.api_key:
            self.notion.api_key = env_notion.api_key
        if env_notion.database_id:
            self.notion.database_id = env_notion.database_id
        if os.environ.get("NOTION_POLL_INTERVAL"):
            self.notion.poll_interval = env_notion.poll_interval

        # GitHub
        env_github = GitHubSettings.from_env()
        if env_github.token:
            self.github.token = env_github.token
        if env_github.owner:
            self.github.owner = env_github.owner
        if env_github.repo:
            self.github.repo = env_github.repo

        # Webhook
        env_webhook = WebhookSettings.from_env()
        if env_webhook.url:
            self.webhook.url = env_webhook.url
        if env_webhook.events:
            self.webhook.events = env_webhook.events
        if env_webhook.secret:
            self.webhook.secret = env_webhook.secret

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by dotted key path.

        Args:
            key: Dotted key path (e.g., 'core.default_model', 'daemon.max_concurrent').
            default: Default value if key not found.

        Returns:
            Configuration value or default.

        Example:
            config.get('core.default_model')  # Returns 'sonnet'
            config.get('slack.channel_id', 'general')  # Returns channel or 'general'
        """
        parts = key.split(".")
        obj: Any = self

        for part in parts:
            if hasattr(obj, part):
                obj = getattr(obj, part)
            elif isinstance(obj, dict) and part in obj:
                obj = obj[part]
            else:
                return default

        return obj

    def set(self, key: str, value: Any) -> bool:
        """Set a configuration value by dotted key path.

        Args:
            key: Dotted key path (e.g., 'core.default_model').
            value: Value to set.

        Returns:
            True if set successfully, False otherwise.

        Example:
            config.set('core.default_model', 'opus')
            config.set('daemon.max_concurrent', 5)
        """
        parts = key.split(".")
        if len(parts) < 2:
            return False

        section_name = parts[0]
        field_name = ".".join(parts[1:])

        if not hasattr(self, section_name):
            return False

        section = getattr(self, section_name)

        # Handle nested keys
        if "." in field_name:
            # For deeply nested, only plugins supports this
            if section_name == "plugins":
                nested_parts = field_name.split(".")
                plugin_name = nested_parts[0]
                if len(nested_parts) == 2:
                    plugin_settings = self.plugins.get(plugin_name)
                    plugin_settings[nested_parts[1]] = value
                    self.plugins.set(plugin_name, plugin_settings)
                    return True
            return False

        if hasattr(section, field_name):
            setattr(section, field_name, value)
            return True

        return False


# =============================================================================
# Configuration Loading/Saving
# =============================================================================


def get_config_path() -> Path:
    """Get the path to the configuration file."""
    if custom_path := os.environ.get("ADW_CONFIG"):
        return Path(custom_path)

    config_dir = DEFAULT_CONFIG_DIR
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / DEFAULT_CONFIG_FILE


def load_config(config_path: Path | None = None) -> ADWConfig:
    """Load configuration from TOML file.

    Args:
        config_path: Path to config file. Uses default if not specified.

    Returns:
        ADWConfig object with settings from file and environment.
    """
    path = config_path or get_config_path()

    config = ADWConfig()
    config.config_path = path

    if path.exists():
        try:
            # Use tomllib for reading TOML
            try:
                import tomllib
            except ImportError:
                import tomli as tomllib  # type: ignore

            with open(path, "rb") as f:
                data = tomllib.load(f)

            config = ADWConfig.from_dict(data)
            config.config_path = path
            config.last_modified = datetime.fromtimestamp(path.stat().st_mtime)

        except Exception as e:
            logger.error(f"Failed to load config from {path}: {e}")
            config = ADWConfig()
            config.config_path = path

    # Apply environment overrides
    config.apply_env_overrides()

    return config


def save_config(config: ADWConfig, config_path: Path | None = None) -> bool:
    """Save configuration to TOML file.

    Args:
        config: ADWConfig to save.
        config_path: Path to config file. Uses default if not specified.

    Returns:
        True if saved successfully, False otherwise.
    """
    path = config_path or config.config_path or get_config_path()

    try:
        # Use tomli_w for writing TOML
        try:
            import tomli_w

            path.parent.mkdir(parents=True, exist_ok=True)
            data = config.to_dict(include_secrets=True)

            with open(path, "wb") as f:
                tomli_w.dump(data, f)

            config.config_path = path
            config.last_modified = datetime.now()
            logger.info(f"Saved config to {path}")
            return True

        except ImportError:
            # Fallback: write as simple TOML manually
            logger.warning("tomli-w not installed, using simple TOML writer")
            return _write_simple_toml(config, path)

    except Exception as e:
        logger.error(f"Failed to save config: {e}")
        return False


def _write_simple_toml(config: ADWConfig, path: Path) -> bool:
    """Write config as simple TOML without tomli-w."""
    try:
        lines = []
        lines.append("# ADW Configuration")
        lines.append(f"# Generated: {datetime.now().isoformat()}")
        lines.append("")

        data = config.to_dict(include_secrets=True)

        for section, values in data.items():
            if isinstance(values, dict):
                # Check if it's a nested section (plugins.xyz)
                has_nested = any(isinstance(v, dict) for v in values.values())

                if has_nested:
                    for subsection, subvalues in values.items():
                        if isinstance(subvalues, dict):
                            lines.append(f"[{section}.{subsection}]")
                            for k, v in subvalues.items():
                                lines.append(f"{k} = {_toml_value(v)}")
                            lines.append("")
                else:
                    lines.append(f"[{section}]")
                    for k, v in values.items():
                        lines.append(f"{k} = {_toml_value(v)}")
                    lines.append("")

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines))
        return True

    except Exception as e:
        logger.error(f"Failed to write simple TOML: {e}")
        return False


def _toml_value(v: Any) -> str:
    """Convert Python value to TOML string."""
    if isinstance(v, bool):
        return "true" if v else "false"
    elif isinstance(v, str):
        # Escape quotes and special characters
        escaped = v.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    elif isinstance(v, (int, float)):
        return str(v)
    elif isinstance(v, list):
        return "[" + ", ".join(_toml_value(x) for x in v) + "]"
    elif v is None:
        return '""'
    return str(v)


def get_config() -> ADWConfig:
    """Get the singleton configuration instance.

    Loads from file on first call, returns cached instance after.
    Use reload_config() to force reload.

    Returns:
        ADWConfig singleton instance.
    """
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reload_config() -> ADWConfig:
    """Force reload configuration from file.

    Returns:
        Newly loaded ADWConfig instance.
    """
    global _config
    _config = load_config()
    return _config


def reset_config() -> None:
    """Reset singleton to force reload on next access."""
    global _config
    _config = None


# =============================================================================
# CLI Helpers
# =============================================================================


def format_config_for_display(config: ADWConfig, show_secrets: bool = False) -> str:
    """Format configuration for CLI display.

    Args:
        config: Configuration to format.
        show_secrets: If True, show sensitive values (masked by default).

    Returns:
        Formatted string for display.
    """
    lines = []
    lines.append("ADW Configuration")
    lines.append("=" * 50)
    lines.append("")

    if config.config_path:
        lines.append(f"Config file: {config.config_path}")
        if config.last_modified:
            lines.append(f"Last modified: {config.last_modified.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

    # Core
    lines.append("[core]")
    lines.append(f"  tasks_file = {config.core.tasks_file}")
    lines.append(f"  default_workflow = {config.core.default_workflow}")
    lines.append(f"  default_model = {config.core.default_model}")
    lines.append("")

    # Daemon
    lines.append("[daemon]")
    lines.append(f"  poll_interval = {config.daemon.poll_interval}")
    lines.append(f"  max_concurrent = {config.daemon.max_concurrent}")
    lines.append(f"  auto_start = {config.daemon.auto_start}")
    lines.append("")

    # UI
    lines.append("[ui]")
    lines.append(f"  show_logo = {config.ui.show_logo}")
    lines.append(f"  theme = {config.ui.theme}")
    lines.append(f"  log_level = {config.ui.log_level}")
    lines.append("")

    # Workflow
    lines.append("[workflow]")
    lines.append(f"  default_timeout = {config.workflow.default_timeout}")
    lines.append(f"  default_retries = {config.workflow.default_retries}")
    lines.append(f"  enable_checkpoints = {config.workflow.enable_checkpoints}")
    lines.append("")

    # Workspace
    lines.append("[workspace]")
    lines.append(f"  enable_worktrees = {config.workspace.enable_worktrees}")
    lines.append(f"  default_branch = {config.workspace.default_branch}")
    lines.append(f"  active_workspace = {config.workspace.active_workspace}")
    lines.append("")

    # Integrations
    lines.append("[integrations]")

    # Slack
    if config.slack.is_configured:
        lines.append("  slack: configured")
        if show_secrets:
            lines.append(f"    bot_token = {config.slack.bot_token[:10]}...")
        if config.slack.channel_id:
            lines.append(f"    channel_id = {config.slack.channel_id}")
    else:
        lines.append("  slack: not configured")

    # Linear
    if config.linear.is_configured:
        lines.append("  linear: configured")
        if config.linear.team_id:
            lines.append(f"    team_id = {config.linear.team_id}")
        lines.append(f"    poll_interval = {config.linear.poll_interval}")
    else:
        lines.append("  linear: not configured")

    # Notion
    if config.notion.is_configured:
        lines.append("  notion: configured")
        if config.notion.database_id:
            lines.append(f"    database_id = {config.notion.database_id[:8]}...")
        lines.append(f"    poll_interval = {config.notion.poll_interval}")
    else:
        lines.append("  notion: not configured")

    # Webhook
    if config.webhook.is_configured:
        lines.append("  webhook: configured")
        lines.append(f"    url = {config.webhook.url}")
        lines.append(f"    events = {', '.join(config.webhook.events)}")
    else:
        lines.append("  webhook: not configured")

    lines.append("")

    # Plugins
    if config.plugins.settings:
        lines.append("[plugins]")
        for name, settings in config.plugins.settings.items():
            enabled = settings.get("enabled", True)
            status = "enabled" if enabled else "disabled"
            lines.append(f"  {name}: {status}")
    else:
        lines.append("[plugins]")
        lines.append("  (none configured)")

    return "\n".join(lines)


def list_config_keys() -> list[str]:
    """List all available configuration keys.

    Returns:
        List of dotted key paths.
    """
    keys = []

    # Core
    keys.extend([
        "core.tasks_file",
        "core.default_workflow",
        "core.default_model",
        "core.project_root",
        "core.auto_detect_type",
    ])

    # Daemon
    keys.extend([
        "daemon.poll_interval",
        "daemon.max_concurrent",
        "daemon.auto_start",
        "daemon.notifications",
        "daemon.webhooks",
    ])

    # UI
    keys.extend([
        "ui.show_logo",
        "ui.theme",
        "ui.notification_sound_success",
        "ui.notification_sound_failure",
        "ui.notification_on_start",
        "ui.log_level",
    ])

    # Workflow
    keys.extend([
        "workflow.default_timeout",
        "workflow.default_retries",
        "workflow.test_timeout",
        "workflow.enable_checkpoints",
        "workflow.enable_wip_commits",
    ])

    # Workspace
    keys.extend([
        "workspace.enable_worktrees",
        "workspace.default_branch",
        "workspace.auto_cleanup",
        "workspace.active_workspace",
    ])

    # Slack
    keys.extend([
        "slack.bot_token",
        "slack.signing_secret",
        "slack.channel_id",
    ])

    # Linear
    keys.extend([
        "linear.api_key",
        "linear.team_id",
        "linear.poll_interval",
        "linear.sync_comments",
    ])

    # Notion
    keys.extend([
        "notion.api_key",
        "notion.database_id",
        "notion.poll_interval",
    ])

    # GitHub
    keys.extend([
        "github.token",
        "github.owner",
        "github.repo",
        "github.poll_interval",
    ])

    # Webhook
    keys.extend([
        "webhook.url",
        "webhook.secret",
    ])

    return keys
