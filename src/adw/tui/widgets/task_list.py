"""Task list widget."""

from __future__ import annotations

from textual.widgets import ListView, ListItem, Static
from textual.message import Message
from rich.text import Text

from ..state import TaskState
from ...agent.models import TaskStatus


STATUS_ICONS = {
    TaskStatus.PENDING: ("⏳", "dim"),
    TaskStatus.BLOCKED: ("⏰", "yellow"),
    TaskStatus.IN_PROGRESS: ("🟡", "cyan"),
    TaskStatus.DONE: ("✅", "green"),
    TaskStatus.FAILED: ("❌", "red"),
}


class TaskListItem(ListItem):
    """Single task item."""

    def __init__(self, task: TaskState, key: str):
        super().__init__()
        self.task = task
        self.task_key = key

    def compose(self):
        icon, style = STATUS_ICONS.get(self.task.status, ("•", "white"))
        text = Text()
        text.append(f"{icon} ", style="bold")
        text.append(f"{self.task.display_id} ", style="dim")
        text.append(self.task.description[:35], style=style)
        yield Static(text)


class TaskList(ListView):
    """List of tasks."""

    class TaskSelected(Message):
        """Task selected message."""
        def __init__(self, key: str):
            super().__init__()
            self.key = key

    def update_tasks(self, tasks: dict[str, TaskState]) -> None:
        """Update displayed tasks."""
        self.clear()
        # Sort: running first, then pending, then done
        def sort_key(item):
            k, t = item
            order = {
                TaskStatus.IN_PROGRESS: 0,
                TaskStatus.PENDING: 1,
                TaskStatus.BLOCKED: 2,
                TaskStatus.FAILED: 3,
                TaskStatus.DONE: 4,
            }
            return (order.get(t.status, 5), k)

        for key, task in sorted(tasks.items(), key=sort_key):
            self.append(TaskListItem(task, key))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle selection."""
        if isinstance(event.item, TaskListItem):
            self.post_message(self.TaskSelected(event.item.task_key))
