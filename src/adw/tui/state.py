"""Reactive state management for TUI."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable
from pathlib import Path
from enum import Enum
import re

from ..agent.models import TaskStatus as AgentTaskStatus
from ..tasks import load_tasks as load_tasks_cli, TaskStatus as CLITaskStatus


class BlockedReason(str, Enum):
    """Reason a task is blocked."""
    DEPENDENCY = "dependency"
    APPROVAL = "approval"
    EXTERNAL = "external"
    QUESTION = "question"
    ERROR = "error"
    MANUAL = "manual"


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
    
    # Blocked fields
    blocked_reason: BlockedReason | None = None
    blocked_message: str | None = None
    blocked_needs: list[str] = field(default_factory=list)
    blocked_since: datetime | None = None
    blocked_by: str | None = None

    @property
    def is_running(self) -> bool:
        return self.status == AgentTaskStatus.IN_PROGRESS

    @property
    def is_blocked(self) -> bool:
        return self.status == AgentTaskStatus.BLOCKED

    @property
    def blocked_summary(self) -> str:
        """Short summary of why blocked."""
        if not self.is_blocked:
            return ""
        if self.blocked_message:
            return self.blocked_message[:50]
        if self.blocked_reason:
            return self.blocked_reason.value
        return "Unknown reason"

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

    def block_task(self, adw_id: str, reason: BlockedReason, message: str, needs: list[str] | None = None) -> bool:
        """Block a task with reason and requirements."""
        tasks_file = Path("tasks.md")
        if not tasks_file.exists():
            return False

        content = tasks_file.read_text()
        
        # Pattern to match task line
        pattern = re.compile(
            rf'\[([🟢🟡⚪]), ({adw_id})\]\s+(.+?)(?=\n\[|$)',
            re.DOTALL
        )

        def replace_task(match):
            description = match.group(3).split('\n')[0].strip()
            block = f"[🔴, {adw_id}, blocked:{reason.value}] {description}\n"
            block += f"  > Blocked: {message}\n"
            if needs:
                block += f"  > Needs: {', '.join(needs)}\n"
            return block

        new_content = pattern.sub(replace_task, content)

        if new_content != content:
            tasks_file.write_text(new_content)
            self.load_from_tasks_md()
            return True

        return False

    def unblock_task(self, adw_id: str, new_status: AgentTaskStatus = AgentTaskStatus.PENDING) -> bool:
        """Unblock a task."""
        tasks_file = Path("tasks.md")
        if not tasks_file.exists():
            return False

        content = tasks_file.read_text()

        emoji = {
            AgentTaskStatus.PENDING: '🟡',
            AgentTaskStatus.IN_PROGRESS: '🟢',
        }.get(new_status, '🟡')

        # Match task with blocked info
        pattern = re.compile(
            rf'\[🔴, ({adw_id})(?:, blocked:\w+)?\]\s+(.+?)(?:\n\s*>.*)*(?=\n\[|\n\n|$)',
            re.DOTALL
        )

        def replace_task(match):
            description = match.group(2).split('\n')[0].strip()
            return f"[{emoji}, {adw_id}] {description}"

        new_content = pattern.sub(replace_task, content)

        if new_content != content:
            tasks_file.write_text(new_content)
            self.load_from_tasks_md()
            return True

        return False
