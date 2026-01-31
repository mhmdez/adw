"""Reactive state management for TUI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable
from pathlib import Path

from ..agent.models import Task, TaskStatus
from ..agent.task_parser import get_all_tasks


@dataclass
class TaskState:
    """State for a single task in TUI."""
    adw_id: str | None
    description: str
    status: TaskStatus
    worktree: str | None = None
    phase: str | None = None
    progress: float = 0.0
    pid: int | None = None

    @property
    def is_running(self) -> bool:
        return self.status == TaskStatus.IN_PROGRESS

    @property
    def display_id(self) -> str:
        return self.adw_id[:8] if self.adw_id else "--------"


@dataclass
class AppState:
    """Global application state."""
    tasks: dict[str, TaskState] = field(default_factory=dict)
    selected_task_id: str | None = None
    focused_panel: str = "tasks"

    _subscribers: list[Callable] = field(default_factory=list, repr=False)

    def subscribe(self, callback: Callable) -> None:
        """Subscribe to state changes."""
        self._subscribers.append(callback)

    def notify(self) -> None:
        """Notify subscribers of change."""
        for cb in self._subscribers:
            cb(self)

    def load_from_tasks_md(self, path: Path | None = None) -> None:
        """Load state from tasks.md."""
        self.tasks.clear()
        for task in get_all_tasks(path):
            key = task.adw_id or f"pending-{task.line_number}"
            self.tasks[key] = TaskState(
                adw_id=task.adw_id,
                description=task.description,
                status=task.status,
                worktree=task.worktree_name,
            )
        self.notify()

    def update_task(self, key: str, **updates) -> None:
        """Update a task."""
        if key in self.tasks:
            for k, v in updates.items():
                setattr(self.tasks[key], k, v)
            self.notify()

    def select_task(self, key: str | None) -> None:
        """Select a task."""
        self.selected_task_id = key
        self.notify()

    @property
    def selected_task(self) -> TaskState | None:
        """Get selected task."""
        if self.selected_task_id:
            return self.tasks.get(self.selected_task_id)
        return None

    @property
    def running_count(self) -> int:
        """Count of running tasks."""
        return sum(1 for t in self.tasks.values() if t.is_running)
