"""Notification system for ADW reports and events.

This module provides functionality for sending notifications to
various channels (Slack, Discord) when events occur.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

# Config file location
CONFIG_PATH = Path.home() / ".adw" / "notifications.json"


class NotificationEvent(Enum):
    """Types of notification events."""

    TASK_START = "task_start"
    TASK_COMPLETE = "task_complete"
    TASK_FAILED = "task_failed"
    DAILY_SUMMARY = "daily_summary"
    WEEKLY_DIGEST = "weekly_digest"
    ANOMALY_DETECTED = "anomaly_detected"
    ERROR = "error"


@dataclass
class NotificationChannel:
    """Configuration for a notification channel.

    Attributes:
        name: Display name for the channel.
        type: Channel type (slack, discord).
        webhook_url: Webhook URL for posting messages.
        enabled: Whether the channel is enabled.
        events: List of events to notify on (empty = all events).
    """

    name: str
    type: str
    webhook_url: str
    enabled: bool = True
    events: list[str] = field(default_factory=list)

    def should_notify(self, event: NotificationEvent) -> bool:
        """Check if this channel should notify for the given event.

        Args:
            event: The notification event.

        Returns:
            True if should notify, False otherwise.
        """
        if not self.enabled:
            return False
        if not self.events:
            return True
        return event.value in self.events

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "type": self.type,
            "webhook_url": self.webhook_url,
            "enabled": self.enabled,
            "events": self.events,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NotificationChannel:
        """Create from dictionary."""
        return cls(
            name=data["name"],
            type=data["type"],
            webhook_url=data["webhook_url"],
            enabled=data.get("enabled", True),
            events=data.get("events", []),
        )


@dataclass
class NotificationConfig:
    """Global notification configuration.

    Attributes:
        enabled: Master switch for all notifications.
        channels: List of configured channels.
    """

    enabled: bool = True
    channels: list[NotificationChannel] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "enabled": self.enabled,
            "channels": [c.to_dict() for c in self.channels],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NotificationConfig:
        """Create from dictionary."""
        return cls(
            enabled=data.get("enabled", True),
            channels=[NotificationChannel.from_dict(c) for c in data.get("channels", [])],
        )


def _load_config() -> NotificationConfig:
    """Load notification configuration.

    Returns:
        NotificationConfig from file or defaults.
    """
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text())
            return NotificationConfig.from_dict(data)
        except Exception as e:
            logger.warning(f"Failed to load notification config: {e}")

    return NotificationConfig()


def _save_config(config: NotificationConfig) -> None:
    """Save notification configuration.

    Args:
        config: Configuration to save.
    """
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config.to_dict(), indent=2))


def _format_slack_message(
    title: str,
    message: str,
    color: str = "#2eb67d",
    fields: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Format a message for Slack webhook.

    Args:
        title: Message title.
        message: Message body.
        color: Attachment color (hex).
        fields: Optional list of field dicts with title/value.

    Returns:
        Slack message payload.
    """
    attachment: dict[str, Any] = {
        "color": color,
        "title": title,
        "text": message,
        "ts": int(datetime.now().timestamp()),
    }

    if fields:
        attachment["fields"] = [
            {"title": f["title"], "value": f["value"], "short": f.get("short", True)} for f in fields
        ]

    return {"attachments": [attachment]}


def _format_discord_message(
    title: str,
    message: str,
    color: int = 3066993,  # Green
    fields: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Format a message for Discord webhook.

    Args:
        title: Message title.
        message: Message body.
        color: Embed color (decimal).
        fields: Optional list of field dicts with title/value.

    Returns:
        Discord message payload.
    """
    embed: dict[str, Any] = {
        "title": title,
        "description": message,
        "color": color,
        "timestamp": datetime.now().isoformat(),
    }

    if fields:
        embed["fields"] = [{"name": f["title"], "value": f["value"], "inline": f.get("short", True)} for f in fields]

    return {"embeds": [embed]}


def _send_webhook(url: str, payload: dict[str, Any]) -> bool:
    """Send a webhook request.

    Args:
        url: Webhook URL.
        payload: JSON payload to send.

    Returns:
        True if successful, False otherwise.
    """
    try:
        data = json.dumps(payload).encode("utf-8")
        request = Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=10) as response:
            return bool(response.status == 200 or response.status == 204)
    except URLError as e:
        logger.error(f"Failed to send webhook: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending webhook: {e}")
        return False


def send_notification(
    event: NotificationEvent,
    title: str,
    message: str,
    fields: list[dict[str, str]] | None = None,
    config: NotificationConfig | None = None,
) -> dict[str, bool]:
    """Send a notification to all configured channels.

    Args:
        event: The notification event type.
        title: Message title.
        message: Message body.
        fields: Optional field data.
        config: Optional config (loads from file if not provided).

    Returns:
        Dictionary mapping channel names to success status.
    """
    if config is None:
        config = _load_config()

    if not config.enabled:
        return {}

    # Map event types to colors
    color_map = {
        NotificationEvent.TASK_START: ("#3498db", 3447003),  # Blue
        NotificationEvent.TASK_COMPLETE: ("#2eb67d", 3066993),  # Green
        NotificationEvent.TASK_FAILED: ("#e74c3c", 15158332),  # Red
        NotificationEvent.DAILY_SUMMARY: ("#9b59b6", 10181046),  # Purple
        NotificationEvent.WEEKLY_DIGEST: ("#f39c12", 15844367),  # Orange
        NotificationEvent.ANOMALY_DETECTED: ("#e67e22", 15105570),  # Dark orange
        NotificationEvent.ERROR: ("#e74c3c", 15158332),  # Red
    }
    slack_color, discord_color = color_map.get(event, ("#2eb67d", 3066993))

    results = {}

    for channel in config.channels:
        if not channel.should_notify(event):
            continue

        if channel.type == "slack":
            payload = _format_slack_message(title, message, slack_color, fields)
        elif channel.type == "discord":
            payload = _format_discord_message(title, message, discord_color, fields)
        else:
            logger.warning(f"Unknown channel type: {channel.type}")
            continue

        results[channel.name] = _send_webhook(channel.webhook_url, payload)

    return results


def notify_task_start(task_id: str, description: str, workflow: str = "standard") -> dict[str, bool]:
    """Send task start notification.

    Args:
        task_id: The task ID.
        description: Task description.
        workflow: Workflow type.

    Returns:
        Channel success results.
    """
    return send_notification(
        event=NotificationEvent.TASK_START,
        title="🚀 Task Started",
        message=f"Task `{task_id[:8]}` has started execution.",
        fields=[
            {"title": "Description", "value": description[:100]},
            {"title": "Workflow", "value": workflow},
        ],
    )


def notify_task_complete(
    task_id: str,
    description: str,
    duration_str: str,
    commits: int = 0,
) -> dict[str, bool]:
    """Send task completion notification.

    Args:
        task_id: The task ID.
        description: Task description.
        duration_str: Human-readable duration.
        commits: Number of commits generated.

    Returns:
        Channel success results.
    """
    return send_notification(
        event=NotificationEvent.TASK_COMPLETE,
        title="✅ Task Completed",
        message=f"Task `{task_id[:8]}` completed successfully.",
        fields=[
            {"title": "Description", "value": description[:100]},
            {"title": "Duration", "value": duration_str},
            {"title": "Commits", "value": str(commits)},
        ],
    )


def notify_task_failed(
    task_id: str,
    description: str,
    error: str,
    retries: int = 0,
) -> dict[str, bool]:
    """Send task failure notification.

    Args:
        task_id: The task ID.
        description: Task description.
        error: Error message.
        retries: Number of retries attempted.

    Returns:
        Channel success results.
    """
    return send_notification(
        event=NotificationEvent.TASK_FAILED,
        title="❌ Task Failed",
        message=f"Task `{task_id[:8]}` failed after {retries} retries.",
        fields=[
            {"title": "Description", "value": description[:100]},
            {"title": "Error", "value": error[:200]},
            {"title": "Retries", "value": str(retries)},
        ],
    )


def notify_daily_summary(
    date: str,
    tasks_completed: int,
    tasks_failed: int,
    success_rate: float,
    estimated_cost: float,
    time_saved_hours: float,
) -> dict[str, bool]:
    """Send daily summary notification.

    Args:
        date: Summary date.
        tasks_completed: Tasks completed.
        tasks_failed: Tasks failed.
        success_rate: Success rate percentage.
        estimated_cost: Estimated cost in USD.
        time_saved_hours: Estimated time saved.

    Returns:
        Channel success results.
    """
    return send_notification(
        event=NotificationEvent.DAILY_SUMMARY,
        title=f"📊 Daily Summary: {date}",
        message=f"ADW completed {tasks_completed} tasks with {success_rate:.0f}% success rate.",
        fields=[
            {"title": "Completed", "value": str(tasks_completed)},
            {"title": "Failed", "value": str(tasks_failed)},
            {"title": "Success Rate", "value": f"{success_rate:.1f}%"},
            {"title": "Cost", "value": f"${estimated_cost:.2f}"},
            {"title": "Time Saved", "value": f"{time_saved_hours:.1f}h"},
        ],
    )


def notify_weekly_digest(
    week: str,
    tasks_completed: int,
    total_commits: int,
    success_rate: float,
    estimated_cost: float,
    time_saved_hours: float,
    week_over_week_change: float,
) -> dict[str, bool]:
    """Send weekly digest notification.

    Args:
        week: Week identifier (e.g., '2026-W05').
        tasks_completed: Tasks completed.
        total_commits: Total commits.
        success_rate: Success rate percentage.
        estimated_cost: Estimated cost in USD.
        time_saved_hours: Estimated time saved.
        week_over_week_change: WoW change in tasks completed.

    Returns:
        Channel success results.
    """
    direction = "↑" if week_over_week_change > 0 else "↓" if week_over_week_change < 0 else "→"
    return send_notification(
        event=NotificationEvent.WEEKLY_DIGEST,
        title=f"📈 Weekly Digest: {week}",
        message=f"ADW completed {tasks_completed} tasks this week ({direction} {abs(week_over_week_change):.0f}% WoW).",
        fields=[
            {"title": "Completed", "value": str(tasks_completed)},
            {"title": "Commits", "value": str(total_commits)},
            {"title": "Success Rate", "value": f"{success_rate:.1f}%"},
            {"title": "Cost", "value": f"${estimated_cost:.2f}"},
            {"title": "Time Saved", "value": f"{time_saved_hours:.1f}h"},
            {"title": "WoW Change", "value": f"{direction} {abs(week_over_week_change):.1f}%"},
        ],
    )


def notify_anomaly(
    metric_name: str,
    date: str,
    value: float,
    expected_range: str,
) -> dict[str, bool]:
    """Send anomaly detection notification.

    Args:
        metric_name: Name of the metric with anomaly.
        date: Date of the anomaly.
        value: Anomalous value.
        expected_range: Expected value range.

    Returns:
        Channel success results.
    """
    return send_notification(
        event=NotificationEvent.ANOMALY_DETECTED,
        title="🔍 Anomaly Detected",
        message=f"Unusual {metric_name} detected on {date}.",
        fields=[
            {"title": "Metric", "value": metric_name},
            {"title": "Date", "value": date},
            {"title": "Value", "value": f"{value:.2f}"},
            {"title": "Expected", "value": expected_range},
        ],
    )


def add_channel(
    name: str,
    channel_type: str,
    webhook_url: str,
    events: list[str] | None = None,
) -> None:
    """Add a notification channel.

    Args:
        name: Channel display name.
        channel_type: Channel type (slack, discord).
        webhook_url: Webhook URL.
        events: List of events to notify on (None = all).
    """
    config = _load_config()

    # Remove existing channel with same name
    config.channels = [c for c in config.channels if c.name != name]

    config.channels.append(
        NotificationChannel(
            name=name,
            type=channel_type,
            webhook_url=webhook_url,
            enabled=True,
            events=events or [],
        )
    )

    _save_config(config)


def remove_channel(name: str) -> bool:
    """Remove a notification channel.

    Args:
        name: Channel name to remove.

    Returns:
        True if channel was removed, False if not found.
    """
    config = _load_config()
    original_count = len(config.channels)
    config.channels = [c for c in config.channels if c.name != name]

    if len(config.channels) < original_count:
        _save_config(config)
        return True
    return False


def list_channels() -> list[dict[str, Any]]:
    """List all configured channels.

    Returns:
        List of channel configurations.
    """
    config = _load_config()
    return [c.to_dict() for c in config.channels]


def enable_notifications(enabled: bool = True) -> None:
    """Enable or disable all notifications.

    Args:
        enabled: Whether notifications should be enabled.
    """
    config = _load_config()
    config.enabled = enabled
    _save_config(config)


def test_channel(name: str) -> bool:
    """Send a test message to a channel.

    Args:
        name: Channel name to test.

    Returns:
        True if test was successful.
    """
    config = _load_config()

    for channel in config.channels:
        if channel.name == name:
            # Temporarily enable for test
            original_enabled = channel.enabled
            channel.enabled = True

            result = send_notification(
                event=NotificationEvent.TASK_COMPLETE,
                title="🧪 Test Notification",
                message="This is a test notification from ADW.",
                fields=[
                    {"title": "Status", "value": "Working"},
                    {"title": "Channel", "value": name},
                ],
                config=NotificationConfig(enabled=True, channels=[channel]),
            )

            channel.enabled = original_enabled
            return result.get(name, False)

    return False
