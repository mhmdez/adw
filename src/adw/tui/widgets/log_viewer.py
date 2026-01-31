"""Log viewer widget."""

from __future__ import annotations

from textual.widgets import RichLog
from textual.message import Message
from rich.text import Text

from ..log_watcher import LogEvent
from ..log_buffer import LogBuffer
from ..log_formatter import format_event


class LogViewer(RichLog):
    """Display streaming logs."""

    DEFAULT_CSS = """
    LogViewer {
        height: 100%;
        border: none;
        scrollbar-size: 0 0;
    }
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, highlight=True, markup=True, **kwargs)
        self.buffer = LogBuffer()
        self._filter_adw_id: str | None = None

    def on_log_event(self, event: LogEvent) -> None:
        """Handle incoming log event."""
        # Add to buffer
        line = self.buffer.add(event)

        # Check filter
        if self._filter_adw_id and event.adw_id != self._filter_adw_id:
            return

        # Display
        self.write(line)

    def filter_by_agent(self, adw_id: str | None) -> None:
        """Filter logs to specific agent."""
        self._filter_adw_id = adw_id
        self.clear()

        if adw_id:
            lines = self.buffer.get_for_agent(adw_id)
        else:
            lines = self.buffer.get_all()

        for line in lines:
            self.write(line)

    def clear_logs(self) -> None:
        """Clear displayed logs."""
        self.clear()
        self.buffer.clear(self._filter_adw_id)
