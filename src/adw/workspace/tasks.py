"""Cross-repo task management for multi-repo workspaces.

Enables task coordination across multiple repositories with
dependency tracking and unified task queues.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..tasks import Task, TaskStatus, load_tasks, parse_tasks
from .config import RepoConfig, load_workspace

logger = logging.getLogger(__name__)


@dataclass
class CrossRepoTask:
    """A task with repository context for cross-repo coordination."""

    task: Task
    repo: RepoConfig | None = None
    repo_name: str = ""
    cross_repo_deps: list[str] = field(default_factory=list)  # ["repo:task_id", ...]

    @property
    def id(self) -> str:
        """Task ID."""
        return self.task.id

    @property
    def title(self) -> str:
        """Task title."""
        return self.task.title

    @property
    def status(self) -> TaskStatus:
        """Task status."""
        return self.task.status

    @property
    def full_id(self) -> str:
        """Full ID with repo prefix: 'repo:task_id'."""
        if self.repo_name:
            return f"{self.repo_name}:{self.task.id}"
        return self.task.id

    @property
    def is_actionable(self) -> bool:
        """Check if task can be worked on."""
        return self.task.is_actionable

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.task.id,
            "title": self.task.title,
            "status": self.task.status.value,
            "repo": self.repo_name,
            "depends_on": self.task.depends_on,
            "cross_repo_deps": self.cross_repo_deps,
        }


@dataclass
class CrossRepoDependency:
    """A dependency between tasks across repositories."""

    source_repo: str
    source_task_id: str
    target_repo: str
    target_task_id: str

    @property
    def source_full_id(self) -> str:
        """Full source ID: 'repo:task_id'."""
        return f"{self.source_repo}:{self.source_task_id}"

    @property
    def target_full_id(self) -> str:
        """Full target ID: 'repo:task_id'."""
        return f"{self.target_repo}:{self.target_task_id}"

    @classmethod
    def parse(cls, dep_str: str, source_repo: str) -> CrossRepoDependency | None:
        """Parse a dependency string like 'repo:TASK-001' or 'TASK-001'.

        Args:
            dep_str: Dependency string to parse.
            source_repo: Default repo if not specified.

        Returns:
            CrossRepoDependency or None if invalid format.
        """
        if ":" in dep_str:
            parts = dep_str.split(":", 1)
            if len(parts) == 2:
                return cls(
                    source_repo=source_repo,
                    source_task_id="",  # Will be filled by caller
                    target_repo=parts[0],
                    target_task_id=parts[1],
                )
        else:
            # Same-repo dependency
            return cls(
                source_repo=source_repo,
                source_task_id="",
                target_repo=source_repo,
                target_task_id=dep_str,
            )
        return None


@dataclass
class WorkspaceTaskQueue:
    """Unified task queue spanning multiple repositories."""

    tasks: list[CrossRepoTask] = field(default_factory=list)
    by_repo: dict[str, list[CrossRepoTask]] = field(default_factory=dict)
    by_id: dict[str, CrossRepoTask] = field(default_factory=dict)

    @property
    def total_count(self) -> int:
        """Total number of tasks."""
        return len(self.tasks)

    @property
    def pending_count(self) -> int:
        """Number of pending tasks."""
        return sum(1 for t in self.tasks if t.status == TaskStatus.PENDING)

    @property
    def in_progress_count(self) -> int:
        """Number of in-progress tasks."""
        return sum(1 for t in self.tasks if t.status == TaskStatus.IN_PROGRESS)

    def get_actionable(self) -> list[CrossRepoTask]:
        """Get tasks that are ready to be worked on.

        Returns tasks that are pending/in_progress and have all
        dependencies satisfied.
        """
        actionable = []
        for task in self.tasks:
            if not task.is_actionable:
                continue
            if self._has_unsatisfied_deps(task):
                continue
            actionable.append(task)
        return actionable

    def _has_unsatisfied_deps(self, task: CrossRepoTask) -> bool:
        """Check if task has unsatisfied dependencies."""
        # Check local dependencies
        for dep_id in task.task.depends_on:
            dep = self.by_id.get(f"{task.repo_name}:{dep_id}")
            if dep and dep.status != TaskStatus.DONE:
                return True

        # Check cross-repo dependencies
        for dep_str in task.cross_repo_deps:
            dep = self.by_id.get(dep_str)
            if dep and dep.status != TaskStatus.DONE:
                return True

        return False

    def get_blocked_reason(self, task: CrossRepoTask) -> str | None:
        """Get the reason a task is blocked.

        Returns None if task is not blocked.
        """
        if not task.is_actionable:
            return None

        blocking = []

        # Check local dependencies
        for dep_id in task.task.depends_on:
            dep = self.by_id.get(f"{task.repo_name}:{dep_id}")
            if dep and dep.status != TaskStatus.DONE:
                blocking.append(f"{dep_id} ({dep.status.value})")

        # Check cross-repo dependencies
        for dep_str in task.cross_repo_deps:
            dep = self.by_id.get(dep_str)
            if dep and dep.status != TaskStatus.DONE:
                blocking.append(f"{dep_str} ({dep.status.value})")

        if blocking:
            return f"Blocked by: {', '.join(blocking)}"
        return None

    def get_tasks_for_repo(self, repo_name: str) -> list[CrossRepoTask]:
        """Get all tasks for a specific repository."""
        return self.by_repo.get(repo_name, [])

    def get_task(self, full_id: str) -> CrossRepoTask | None:
        """Get a task by full ID (repo:task_id)."""
        return self.by_id.get(full_id)

    def summary(self) -> dict[str, Any]:
        """Get summary statistics."""
        by_status: dict[str, int] = {}
        by_repo_status: dict[str, dict[str, int]] = {}

        for task in self.tasks:
            status = task.status.value
            by_status[status] = by_status.get(status, 0) + 1

            if task.repo_name not in by_repo_status:
                by_repo_status[task.repo_name] = {}
            by_repo_status[task.repo_name][status] = (
                by_repo_status[task.repo_name].get(status, 0) + 1
            )

        return {
            "total": self.total_count,
            "by_status": by_status,
            "by_repo": by_repo_status,
            "actionable": len(self.get_actionable()),
        }


def load_workspace_tasks(config_path: Path | None = None) -> WorkspaceTaskQueue:
    """Load all tasks from all repositories in the workspace.

    Args:
        config_path: Path to workspace config.

    Returns:
        WorkspaceTaskQueue with all tasks indexed.
    """
    config = load_workspace(config_path)
    workspace = config.get_active()

    queue = WorkspaceTaskQueue()

    if not workspace:
        # Fallback to current directory
        tasks = load_tasks()
        current_repo = "current"

        for task in tasks:
            cross_task = CrossRepoTask(
                task=task,
                repo=None,
                repo_name=current_repo,
                cross_repo_deps=_extract_cross_repo_deps(task, current_repo),
            )
            queue.tasks.append(cross_task)
            queue.by_id[cross_task.full_id] = cross_task

            if current_repo not in queue.by_repo:
                queue.by_repo[current_repo] = []
            queue.by_repo[current_repo].append(cross_task)

        return queue

    # Load tasks from each repo
    for repo in workspace.enabled_repos:
        repo_tasks = _load_repo_tasks(repo)

        for task in repo_tasks:
            cross_task = CrossRepoTask(
                task=task,
                repo=repo,
                repo_name=repo.name,
                cross_repo_deps=_extract_cross_repo_deps(task, repo.name),
            )
            queue.tasks.append(cross_task)
            queue.by_id[cross_task.full_id] = cross_task

            if repo.name not in queue.by_repo:
                queue.by_repo[repo.name] = []
            queue.by_repo[repo.name].append(cross_task)

    return queue


def _load_repo_tasks(repo: RepoConfig) -> list[Task]:
    """Load tasks from a repository's tasks.md."""
    if not repo.exists():
        logger.warning(f"Repository path does not exist: {repo.path}")
        return []

    tasks_path = repo.resolved_path / "tasks.md"
    if not tasks_path.exists():
        logger.debug(f"No tasks.md found in {repo.name}")
        return []

    try:
        content = tasks_path.read_text()
        return parse_tasks(content)
    except Exception as e:
        logger.error(f"Failed to load tasks from {repo.name}: {e}")
        return []


def _extract_cross_repo_deps(task: Task, current_repo: str) -> list[str]:
    """Extract cross-repo dependencies from task.

    Cross-repo deps are formatted as 'repo:TASK-ID' in the depends_on list.
    """
    cross_deps = []
    for dep in task.depends_on:
        if ":" in dep:
            # Already fully qualified
            cross_deps.append(dep)
        # Note: same-repo deps are not included here as they're in task.depends_on
    return cross_deps


def detect_repo_from_path(path: Path | str, config_path: Path | None = None) -> str | None:
    """Auto-detect which repository a path belongs to.

    Args:
        path: File or directory path.
        config_path: Path to workspace config.

    Returns:
        Repository name or None if not in workspace.
    """
    target = Path(path).expanduser().resolve()

    config = load_workspace(config_path)
    workspace = config.get_active()

    if not workspace:
        return None

    for repo in workspace.repos:
        repo_path = repo.resolved_path
        try:
            # Check if target is under repo path
            target.relative_to(repo_path)
            return repo.name
        except ValueError:
            continue

    return None


def parse_task_spec(spec: str) -> tuple[str | None, str]:
    """Parse a task specification with optional repo prefix.

    Formats:
        'TASK-001' -> (None, 'TASK-001')
        'frontend:TASK-001' -> ('frontend', 'TASK-001')
        '{repo: frontend} Fix bug' -> ('frontend', 'Fix bug')

    Args:
        spec: Task specification string.

    Returns:
        Tuple of (repo_name, task_description).
    """
    # Check for explicit repo tag
    tag_match = re.match(r"\{repo:\s*(\w+)\}\s*(.+)", spec)
    if tag_match:
        return tag_match.group(1), tag_match.group(2)

    # Check for prefix format
    if ":" in spec:
        parts = spec.split(":", 1)
        # Only treat as repo prefix if first part looks like a repo name (no spaces)
        if len(parts) == 2 and " " not in parts[0]:
            return parts[0], parts[1].strip()

    return None, spec


def add_cross_repo_task(
    description: str,
    repo_name: str | None = None,
    depends_on: list[str] | None = None,
    config_path: Path | None = None,
) -> bool:
    """Add a task to a repository's tasks.md.

    Args:
        description: Task description.
        repo_name: Target repository (uses current directory if None).
        depends_on: List of dependencies (can include 'repo:task_id').
        config_path: Path to workspace config.

    Returns:
        True if task was added successfully.
    """
    config = load_workspace(config_path)
    workspace = config.get_active()

    # Determine target path
    if repo_name and workspace:
        repo = workspace.get_repo(repo_name)
        if not repo:
            logger.error(f"Repository not found: {repo_name}")
            return False
        tasks_path = repo.resolved_path / "tasks.md"
    else:
        tasks_path = Path.cwd() / "tasks.md"

    # Create tasks.md if it doesn't exist
    if not tasks_path.exists():
        tasks_path.write_text("# Tasks\n\n")

    content = tasks_path.read_text()

    # Generate task ID
    existing_ids = re.findall(r"TASK-(\d+)", content)
    next_num = max([int(n) for n in existing_ids], default=0) + 1
    task_id = f"TASK-{next_num:03d}"

    # Build task line
    task_line = f"- [ ] {task_id}: {description}"

    # Add dependency metadata if any
    if depends_on:
        task_line += f"\n  - Depends: {', '.join(depends_on)}"

    # Append to file
    if content.endswith("\n"):
        new_content = content + task_line + "\n"
    else:
        new_content = content + "\n" + task_line + "\n"

    tasks_path.write_text(new_content)
    logger.info(f"Added task {task_id} to {tasks_path}")
    return True
