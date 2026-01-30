"""Task parsing and management for ADW."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class TaskStatus(Enum):
    """Task status values."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"
    FAILED = "failed"


@dataclass
class Task:
    """A task parsed from tasks.md."""

    id: str
    title: str
    status: TaskStatus
    description: str = ""
    spec: str | None = None
    assignee: str | None = None
    depends_on: list[str] = field(default_factory=list)
    subtasks: list[Task] = field(default_factory=list)
    raw_line: str = ""

    @property
    def is_actionable(self) -> bool:
        """Check if task can be worked on (pending or in_progress)."""
        return self.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS)


def parse_tasks(content: str) -> list[Task]:
    """Parse tasks from tasks.md content.

    Expected format:
    ```markdown
    ## Tasks

    - [ ] TASK-001: Implement feature X
      - Status: pending
      - Spec: specs/feature-x.md
      - [ ] Subtask 1
      - [x] Subtask 2 (done)
    - [x] TASK-002: Setup project (done)
    - [-] TASK-003: Blocked task (blocked)
    ```

    Args:
        content: Raw markdown content from tasks.md.

    Returns:
        List of parsed Task objects.
    """
    tasks: list[Task] = []

    # Pattern for task lines: - [ ] TASK-XXX: Title or - [x] TASK-XXX: Title
    status_values = r"pending|in_progress|done|blocked|failed"
    task_pattern = re.compile(
        rf"^-\s+\[([ xX\-!])\]\s+(?:([A-Z]+-\d+):\s+)?(.+?)(?:\s+\(({status_values})\))?$"
    )

    # Pattern for metadata lines: - Status: value
    metadata_pattern = re.compile(r"^\s+-\s+(Status|Spec|Assignee|Depends):\s+(.+)$", re.IGNORECASE)

    # Pattern for subtask lines: indented - [ ] text
    subtask_pattern = re.compile(r"^\s+-\s+\[([ xX])\]\s+(.+)$")

    current_task: Task | None = None
    lines = content.split("\n")
    task_counter = 1

    for line in lines:
        # Try to match a task line
        task_match = task_pattern.match(line)
        if task_match:
            checkbox, task_id, title, explicit_status = task_match.groups()

            # Determine status from checkbox or explicit status
            if explicit_status:
                status = TaskStatus(explicit_status)
            elif checkbox in ("x", "X"):
                status = TaskStatus.DONE
            elif checkbox == "-":
                status = TaskStatus.BLOCKED
            elif checkbox == "!":
                status = TaskStatus.FAILED
            else:
                status = TaskStatus.PENDING

            # Generate task ID if not provided
            if not task_id:
                task_id = f"TASK-{task_counter:03d}"
                task_counter += 1

            current_task = Task(
                id=task_id,
                title=title.strip(),
                status=status,
                raw_line=line,
            )
            tasks.append(current_task)
            continue

        # Try to match metadata for current task
        if current_task:
            metadata_match = metadata_pattern.match(line)
            if metadata_match:
                key, value = metadata_match.groups()
                key = key.lower()
                if key == "status":
                    try:
                        current_task.status = TaskStatus(value.lower())
                    except ValueError:
                        pass
                elif key == "spec":
                    current_task.spec = value
                elif key == "assignee":
                    current_task.assignee = value
                elif key == "depends":
                    current_task.depends_on = [d.strip() for d in value.split(",")]
                continue

            # Try to match subtask
            subtask_match = subtask_pattern.match(line)
            if subtask_match:
                checkbox, subtask_title = subtask_match.groups()
                subtask_status = TaskStatus.DONE if checkbox in ("x", "X") else TaskStatus.PENDING
                subtask = Task(
                    id=f"{current_task.id}-{len(current_task.subtasks) + 1}",
                    title=subtask_title.strip(),
                    status=subtask_status,
                    raw_line=line,
                )
                current_task.subtasks.append(subtask)

    return tasks


def load_tasks(path: Path | None = None) -> list[Task]:
    """Load tasks from tasks.md file.

    Args:
        path: Path to tasks.md. Defaults to ./tasks.md.

    Returns:
        List of parsed Task objects.

    Raises:
        FileNotFoundError: If tasks.md doesn't exist.
    """
    if path is None:
        path = Path.cwd() / "tasks.md"

    if not path.exists():
        return []

    content = path.read_text()
    return parse_tasks(content)


def get_tasks_summary(tasks: list[Task]) -> dict[str, int]:
    """Get a summary of task counts by status.

    Args:
        tasks: List of tasks.

    Returns:
        Dictionary mapping status to count.
    """
    summary: dict[str, int] = {
        "total": len(tasks),
        "pending": 0,
        "in_progress": 0,
        "done": 0,
        "blocked": 0,
        "failed": 0,
    }

    for task in tasks:
        summary[task.status.value] += 1

    return summary


def update_task_status(
    task_id: str,
    new_status: TaskStatus,
    path: Path | None = None,
) -> bool:
    """Update a task's status in tasks.md.

    Args:
        task_id: The task ID to update.
        new_status: The new status.
        path: Path to tasks.md. Defaults to ./tasks.md.

    Returns:
        True if task was found and updated.
    """
    if path is None:
        path = Path.cwd() / "tasks.md"

    if not path.exists():
        return False

    content = path.read_text()
    lines = content.split("\n")
    updated = False

    # Map status to checkbox character
    checkbox_map = {
        TaskStatus.PENDING: " ",
        TaskStatus.IN_PROGRESS: " ",
        TaskStatus.DONE: "x",
        TaskStatus.BLOCKED: "-",
        TaskStatus.FAILED: "!",
    }

    status_values = r"pending|in_progress|done|blocked|failed"
    escaped_id = re.escape(task_id)
    task_pattern = re.compile(
        rf"^(-\s+\[)([ xX\-!])(\]\s+(?:{escaped_id}:\s+)?(.+?))(\s+\(({status_values})\))?$"
    )

    for i, line in enumerate(lines):
        match = task_pattern.match(line)
        if match:
            prefix, _, middle, title, status_suffix = match.groups()
            new_checkbox = checkbox_map[new_status]

            # Add status suffix for non-obvious statuses
            if new_status == TaskStatus.IN_PROGRESS:
                new_suffix = " (in_progress)"
            elif new_status == TaskStatus.FAILED:
                new_suffix = " (failed)"
            elif new_status in (TaskStatus.PENDING, TaskStatus.DONE, TaskStatus.BLOCKED):
                new_suffix = ""
            else:
                new_suffix = ""

            lines[i] = f"{prefix}{new_checkbox}{middle}{new_suffix}"
            updated = True
            break

    if updated:
        path.write_text("\n".join(lines))

    return updated
