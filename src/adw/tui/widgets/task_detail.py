"""Task detail widget."""

from __future__ import annotations

from textual.widgets import Static
from textual.containers import Vertical
from textual.app import ComposeResult
from rich.text import Text
from rich.panel import Panel

from ..state import TaskState


class TaskDetail(Static):
    """Display details for selected task."""

    DEFAULT_CSS = """
    TaskDetail {
        height: 100%;
        padding: 1;
    }
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._task: TaskState | None = None

    def update_task(self, task: TaskState | None) -> None:
        """Update displayed task."""
        self._task = task
        self.refresh()

    def render(self) -> Text:
        """Render task details."""
        if not self._task:
            return Text("No task selected", style="dim")

        t = self._task
        lines = []

        lines.append(("ID: ", "bold"))
        lines.append((t.display_id, "cyan"))
        lines.append(("\n", ""))

        lines.append(("Status: ", "bold"))
        status_style = {
            "pending": "dim",
            "blocked": "yellow",
            "in_progress": "cyan",
            "done": "green",
            "failed": "red",
        }.get(t.status.value, "white")
        lines.append((t.status.value.replace("_", " ").title(), status_style))
        lines.append(("\n", ""))

        if t.worktree:
            lines.append(("Worktree: ", "bold"))
            lines.append((t.worktree, ""))
            lines.append(("\n", ""))

        if t.phase:
            lines.append(("Phase: ", "bold"))
            lines.append((t.phase, ""))
            lines.append(("\n", ""))

        lines.append(("\nDescription:\n", "bold"))
        lines.append((t.description, ""))

        text = Text()
        for content, style in lines:
            text.append(content, style=style)

        return text
