"""Webhook callbacks for ADW task events.

Sends HTTP POST requests when tasks start/complete/fail.
Supports Slack, Discord, and generic webhooks.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable
from urllib.request import Request, urlopen
from urllib.error import URLError


class WebhookType(str, Enum):
    """Webhook format type."""
    GENERIC = "generic"
    SLACK = "slack"
    DISCORD = "discord"


@dataclass
class WebhookConfig:
    """Configuration for webhooks."""
    url: str
    type: WebhookType = WebhookType.GENERIC
    enabled: bool = True
    events: list[str] = field(default_factory=lambda: ["task_completed", "task_failed"])
    timeout: float = 10.0
    include_logs: bool = False  # Include agent output in payload


def detect_webhook_type(url: str) -> WebhookType:
    """Detect webhook type from URL."""
    if "hooks.slack.com" in url:
        return WebhookType.SLACK
    elif "discord.com/api/webhooks" in url or "discordapp.com/api/webhooks" in url:
        return WebhookType.DISCORD
    return WebhookType.GENERIC


def format_slack_payload(event: str, data: dict) -> dict:
    """Format payload for Slack webhook."""
    if event == "task_completed":
        emoji = "✅"
        color = "#36a64f"
        title = "ADW Task Completed"
    elif event == "task_failed":
        emoji = "❌"
        color = "#ff0000"
        title = "ADW Task Failed"
    elif event == "task_started":
        emoji = "🚀"
        color = "#0066cc"
        title = "ADW Task Started"
    else:
        emoji = "ℹ️"
        color = "#808080"
        title = f"ADW Event: {event}"
    
    desc = data.get("description", "Unknown task")[:100]
    adw_id = data.get("adw_id", "unknown")[:8]
    
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{emoji} *{title}*\n\n{desc}"
            }
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"ADW ID: `{adw_id}`"},
                {"type": "mrkdwn", "text": f"Time: {datetime.now().strftime('%H:%M:%S')}"}
            ]
        }
    ]
    
    if event == "task_failed":
        error = data.get("error") or f"Exit code {data.get('return_code', '?')}"
        blocks.insert(1, {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Error:* {error[:200]}"}
        })
    
    return {
        "attachments": [{"color": color, "blocks": blocks}]
    }


def format_discord_payload(event: str, data: dict) -> dict:
    """Format payload for Discord webhook."""
    if event == "task_completed":
        color = 0x36a64f  # Green
        title = "✅ ADW Task Completed"
    elif event == "task_failed":
        color = 0xff0000  # Red
        title = "❌ ADW Task Failed"
    elif event == "task_started":
        color = 0x0066cc  # Blue
        title = "🚀 ADW Task Started"
    else:
        color = 0x808080  # Gray
        title = f"ℹ️ ADW Event: {event}"
    
    desc = data.get("description", "Unknown task")[:100]
    adw_id = data.get("adw_id", "unknown")[:8]
    
    fields = [
        {"name": "ADW ID", "value": f"`{adw_id}`", "inline": True},
        {"name": "Time", "value": datetime.now().strftime("%H:%M:%S"), "inline": True}
    ]
    
    if event == "task_failed":
        error = data.get("error") or f"Exit code {data.get('return_code', '?')}"
        fields.append({"name": "Error", "value": error[:200], "inline": False})
    
    return {
        "embeds": [{
            "title": title,
            "description": desc,
            "color": color,
            "fields": fields,
            "footer": {"text": "ADW - AI Developer Workflow"}
        }]
    }


def format_generic_payload(event: str, data: dict) -> dict:
    """Format generic JSON payload."""
    return {
        "event": event,
        "timestamp": datetime.now().isoformat(),
        "data": {
            "adw_id": data.get("adw_id"),
            "description": data.get("description"),
            "error": data.get("error"),
            "return_code": data.get("return_code"),
            "stderr": data.get("stderr", "")[:500] if data.get("stderr") else None,
        }
    }


def send_webhook(
    config: WebhookConfig,
    event: str,
    data: dict,
) -> bool:
    """Send webhook request.
    
    Args:
        config: Webhook configuration
        event: Event type (task_started, task_completed, task_failed)
        data: Event data dict
        
    Returns:
        True if webhook was sent successfully
    """
    if not config.enabled:
        return False
    
    if event not in config.events:
        return False
    
    # Format payload based on type
    if config.type == WebhookType.SLACK:
        payload = format_slack_payload(event, data)
    elif config.type == WebhookType.DISCORD:
        payload = format_discord_payload(event, data)
    else:
        payload = format_generic_payload(event, data)
    
    try:
        req = Request(
            config.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "ADW-CLI/0.3.1"
            },
            method="POST",
        )
        
        with urlopen(req, timeout=config.timeout) as resp:
            return resp.status < 400
    except (URLError, TimeoutError, Exception):
        return False


class WebhookHandler:
    """Event handler for ADW webhooks.
    
    Subscribe this to a CronDaemon to send webhook notifications.
    
    Usage:
        daemon = CronDaemon(config)
        webhook_handler = WebhookHandler(webhook_url="https://...")
        daemon.subscribe(webhook_handler.on_event)
    """
    
    def __init__(
        self,
        webhook_url: str | None = None,
        webhook_type: WebhookType | None = None,
        events: list[str] | None = None,
    ):
        # Try environment variables if not provided
        url = webhook_url or os.environ.get("ADW_WEBHOOK_URL")
        
        if not url:
            self.config = None
            return
        
        detected_type = webhook_type or detect_webhook_type(url)
        
        self.config = WebhookConfig(
            url=url,
            type=detected_type,
            events=events or ["task_completed", "task_failed"],
        )
    
    def on_event(self, event: str, data: dict) -> None:
        """Handle daemon/manager events."""
        if not self.config:
            return
        
        send_webhook(self.config, event, data)


def load_webhook_from_env() -> WebhookHandler | None:
    """Load webhook config from environment variables.
    
    Environment variables:
        ADW_WEBHOOK_URL: Webhook URL (required)
        ADW_WEBHOOK_EVENTS: Comma-separated events (optional)
    
    Returns:
        WebhookHandler if configured, None otherwise
    """
    url = os.environ.get("ADW_WEBHOOK_URL")
    if not url:
        return None
    
    events_str = os.environ.get("ADW_WEBHOOK_EVENTS", "task_completed,task_failed")
    events = [e.strip() for e in events_str.split(",")]
    
    return WebhookHandler(webhook_url=url, events=events)
