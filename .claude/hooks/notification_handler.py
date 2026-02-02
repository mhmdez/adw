#!/usr/bin/env uv run
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Notification handler for Claude Code events.

Logs notifications to .adw/notifications.jsonl.
Can be extended to send notifications via webhooks, desktop notifications, etc.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path


def get_adw_dir() -> Path:
    """Get .adw directory, creating if needed."""
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    adw_dir = Path(project_dir) / ".adw"
    adw_dir.mkdir(parents=True, exist_ok=True)
    return adw_dir


def log_notification(session_id: str, notification_data: dict) -> None:
    """Log notification to .adw/notifications.jsonl.

    Args:
        session_id: Current session ID.
        notification_data: Notification data from hook input.
    """
    notifications_file = get_adw_dir() / "notifications.jsonl"

    entry = {
        "timestamp": datetime.now().isoformat(),
        "session_id": session_id,
        "type": notification_data.get("type", "unknown"),
        "title": notification_data.get("title"),
        "message": notification_data.get("message"),
        "data": notification_data,
    }

    with open(notifications_file, "a") as f:
        f.write(json.dumps(entry) + "\n")


def main() -> None:
    """Main hook handler."""
    # Read hook input from stdin
    try:
        stdin_data = sys.stdin.read()
        hook_input = json.loads(stdin_data) if stdin_data else {}
    except json.JSONDecodeError:
        hook_input = {}

    session_id = os.environ.get("CLAUDE_SESSION_ID", "unknown")

    # Log the notification
    log_notification(session_id, hook_input)

    # Always allow (notifications are informational)
    sys.exit(0)


if __name__ == "__main__":
    main()
