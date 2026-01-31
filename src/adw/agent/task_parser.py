"""Parse tasks.md into structured task objects."""

from __future__ import annotations

import re
from pathlib import Path

from .models import Task, TaskStatus, Worktree


# Regex patterns
WORKTREE_PATTERN = re.compile(r"^##\s+(?:Worktree[:\s]+)?(.+)$", re.IGNORECASE)
TASK_PATTERN = re.compile(
    r"^\s*(?:-\s+)?\[(?P<status>[^\]]*)\]"
    r"(?:\s*,?\s*(?P<adw_id>[a-f0-9]{8}))?"
    r"(?:\s*,?\s*(?P<commit>[a-f0-9]{7,40}))?"
    r"\s+(?P<description>.+?)"
    r"(?:\s*\{(?P<tags>[^}]+)\})?"
    r"(?:\s*//\s*(?P<error>.+))?"
    r"\s*$"
)


def parse_status(status_str: str) -> TaskStatus:
    """Parse status marker to enum."""
    s = status_str.strip().split(",")[0].strip()

    if not s or s == "":
        return TaskStatus.PENDING
    if "⏰" in s:
        return TaskStatus.BLOCKED
    if "🟡" in s:
        return TaskStatus.IN_PROGRESS
    if "✅" in s:
        return TaskStatus.DONE
    if "❌" in s:
        return TaskStatus.FAILED

    return TaskStatus.PENDING


def parse_tags(tags_str: str | None) -> list[str]:
    """Parse comma-separated tags."""
    if not tags_str:
        return []
    return [t.strip().lower() for t in tags_str.split(",") if t.strip()]


def parse_tasks_md(content: str) -> list[Worktree]:
    """Parse tasks.md content."""
    worktrees: list[Worktree] = []
    current: Worktree | None = Worktree(name="Main")  # Default context

    for line_num, line in enumerate(content.split("\n"), 1):
        line = line.rstrip()

        # Worktree header (or any H2/H3 header as context)
        match = WORKTREE_PATTERN.match(line)
        if match:
            if current and current.tasks:  # Only save if it has tasks
                worktrees.append(current)
            current = Worktree(name=match.group(1).strip())
            continue
        
        # Also catch standard headers as context if no worktree set
        if line.startswith("#") and not match:
             # Just a structural header, we could use it as context if we wanted,
             # but for now let's just stick to the default Main if explicit Worktree missing.
             pass

        # Task line
        match = TASK_PATTERN.match(line)
        if match and current:
            g = match.groupdict()
            task = Task(
                description=g["description"].strip(),
                status=parse_status(g["status"] or ""),
                adw_id=g.get("adw_id"),
                commit_hash=g.get("commit"),
                error_message=g.get("error"),
                tags=parse_tags(g.get("tags")),
                worktree_name=current.name,
                line_number=line_num,
            )
            current.tasks.append(task)

    if current:
        worktrees.append(current)

    return worktrees


def load_tasks(path: Path | None = None) -> list[Worktree]:
    """Load tasks from file."""
    path = path or Path("tasks.md")
    if not path.exists():
        return []
    return parse_tasks_md(path.read_text())


def get_all_tasks(path: Path | None = None) -> list[Task]:
    """Get flat list of all tasks."""
    tasks = []
    for worktree in load_tasks(path):
        tasks.extend(worktree.tasks)
    return tasks


def get_eligible_tasks(path: Path | None = None) -> list[Task]:
    """Get tasks eligible for execution.

    This function collects all eligible tasks across all worktrees.
    Eligibility is determined by the Worktree.get_eligible_tasks() method,
    which enforces dependency checking for blocked tasks.

    Args:
        path: Path to tasks.md file. Defaults to "tasks.md" in current directory.

    Returns:
        Flat list of all eligible tasks from all worktrees.
    """
    eligible = []
    for worktree in load_tasks(path):
        eligible.extend(worktree.get_eligible_tasks())
    return eligible


def has_pending_tasks(path: Path | None = None) -> bool:
    """Quick check for pending tasks."""
    path = path or Path("tasks.md")
    if not path.exists():
        return False
    content = path.read_text()
    return bool(re.search(r"\[\s*\]|\[⏰\]", content))
