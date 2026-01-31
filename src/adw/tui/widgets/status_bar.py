"""Status bar widget with input capability."""

from __future__ import annotations

from textual.widgets import Static, Input
from textual.containers import Horizontal
from textual.app import ComposeResult


class StatusBar(Static):
    """Status bar with message display and input."""

    DEFAULT_CSS = """
    StatusBar {
        height: 3;
        layout: horizontal;
    }

    StatusBar > .status-info {
        width: 30%;
        padding: 1;
    }

    StatusBar > .status-input {
        width: 70%;
        padding: 0 1;
    }

    StatusBar Input {
        width: 100%;
    }
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.active_tasks = 0
        self.selected_task = None

    def compose(self) -> ComposeResult:
        """Create status bar content."""
        with Horizontal():
            yield Static(self._get_status_text(), id="status-info", classes="status-info")
            with Static(classes="status-input"):
                yield Input(placeholder="Type message or command...", id="status-input-field")

    def _get_status_text(self) -> str:
        """Get status display text."""
        if self.selected_task:
            return f"Selected: {self.selected_task}"
        return f"Tasks: {self.active_tasks} active"

    def update_status(self, active_tasks: int = 0, selected_task: str | None = None):
        """Update the status display."""
        self.active_tasks = active_tasks
        self.selected_task = selected_task

        info = self.query_one("#status-info", Static)
        info.update(self._get_status_text())
