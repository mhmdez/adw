"""Format log events for display."""

from __future__ import annotations

from rich.text import Text

from .log_watcher import LogEvent


ICONS = {
    "assistant": "💬",
    "tool": "🔧",
    "tool_result": "✓",
    "result": "✅",
    "error": "❌",
    "file_read": "📖",
    "file_write": "📝",
    "unknown": "•",
}

STYLES = {
    "assistant": "white",
    "tool": "cyan",
    "tool_result": "dim",
    "result": "green",
    "error": "red",
}


def format_event(event: LogEvent) -> Text:
    """Format a log event for display."""
    icon = ICONS.get(event.event_type, "•")
    style = STYLES.get(event.event_type, "white")
    time = event.timestamp.strftime("%H:%M:%S")

    text = Text()
    text.append(f"{time} ", style="dim")
    text.append(f"{icon} ", style="bold")
    text.append(f"[{event.adw_id[:8]}] ", style="cyan dim")
    text.append(event.message[:80], style=style)

    return text
