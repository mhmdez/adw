"""Buffer logs with automatic pruning."""

from __future__ import annotations

from collections import deque
from rich.text import Text

from .log_watcher import LogEvent
from .log_formatter import format_event


class LogBuffer:
    """Buffer log events with max capacity."""

    def __init__(self, max_lines: int = 500):
        self.max_lines = max_lines
        self._buffers: dict[str, deque[Text]] = {}  # adw_id -> lines
        self._all: deque[Text] = deque(maxlen=max_lines)

    def add(self, event: LogEvent) -> Text:
        """Add event to buffer, return formatted line."""
        line = format_event(event)

        # Per-agent buffer
        if event.adw_id not in self._buffers:
            self._buffers[event.adw_id] = deque(maxlen=self.max_lines)
        self._buffers[event.adw_id].append(line)

        # Global buffer
        self._all.append(line)

        return line

    def get_for_agent(self, adw_id: str, count: int = 50) -> list[Text]:
        """Get recent lines for agent."""
        if adw_id not in self._buffers:
            return []
        return list(self._buffers[adw_id])[-count:]

    def get_all(self, count: int = 50) -> list[Text]:
        """Get all recent lines."""
        return list(self._all)[-count:]

    def clear(self, adw_id: str | None = None) -> None:
        """Clear buffer."""
        if adw_id:
            if adw_id in self._buffers:
                self._buffers[adw_id].clear()
        else:
            self._buffers.clear()
            self._all.clear()
