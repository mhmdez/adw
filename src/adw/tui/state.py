"""Reactive state management for TUI."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable
from pathlib import Path

from ..agent.models import TaskStatus as AgentTaskStatus
from ..tasks import load_tasks as load_tasks_cli, TaskStatus as CLITaskStatus


@dataclass
class TaskState:
    """State for a single task in TUI."""
    adw_id: str | None
    description: str
    status: AgentTaskStatus
    worktree: str | None = None
    phase: str | None = None
    progress: float = 0.0
    pid: int | None = None
    started_at: datetime | None = None
    last_activity: str | None = None

    @property
    def is_running(self) -> bool:
        return self.status == AgentTaskStatus.IN_PROGRESS

    @property
    def display_id(self) -> str:
        return self.adw_id[:8] if self.adw_id else "--------"


@dataclass
class AppState:
    """Global application state."""
    tasks: dict[str, TaskState] = field(default_factory=dict)
    selected_task_id: str | None = None
    focused_panel: str = "tasks"
    current_activity: str | None = None
    activity_started_at: datetime | None = None

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

        # Map CLI TaskStatus to Agent TaskStatus
        status_map = {
            CLITaskStatus.PENDING: AgentTaskStatus.PENDING,
            CLITaskStatus.IN_PROGRESS: AgentTaskStatus.IN_PROGRESS,
            CLITaskStatus.DONE: AgentTaskStatus.DONE,
            CLITaskStatus.BLOCKED: AgentTaskStatus.BLOCKED,
            CLITaskStatus.FAILED: AgentTaskStatus.FAILED,
        }

        for i, task in enumerate(load_tasks_cli(path)):
            key = task.id or f"pending-{i}"
            self.tasks[key] = TaskState(
                adw_id=task.id,
                description=task.title,
                status=status_map.get(task.status, AgentTaskStatus.PENDING),
                worktree=None,
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

    @property
    def running_tasks(self) -> list[TaskState]:
        """Get all running tasks."""
        return [t for t in self.tasks.values() if t.is_running]

    def update_activity(self, adw_id: str, activity: str) -> None:
        """Update activity for a task.

        Args:
            adw_id: The ADW ID of the task
            activity: Description of current activity
        """
        # Find task by adw_id
        for key, task in self.tasks.items():
            if task.adw_id and task.adw_id.startswith(adw_id[:8]):
                task.last_activity = activity
                if not task.started_at:
                    task.started_at = datetime.now()
                break

        # Update global activity
        self.current_activity = activity
        if not self.activity_started_at:
            self.activity_started_at = datetime.now()

        self.notify()

    def clear_activity(self) -> None:
        """Clear the current activity."""
        self.current_activity = None
        self.activity_started_at = None
        self.notify()
