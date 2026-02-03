"""Data models for ADW agent system."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "pending"
    BLOCKED = "blocked"
    AWAITING_REVIEW = "awaiting_review"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"


class RetryCode(str, Enum):
    NONE = "none"
    CLAUDE_CODE_ERROR = "claude_code_error"
    TIMEOUT_ERROR = "timeout_error"
    EXECUTION_ERROR = "execution_error"
    RATE_LIMIT = "rate_limit"


class AgentPromptRequest(BaseModel):
    """Request to execute a prompt."""

    prompt: str
    adw_id: str
    agent_name: str = "default"
    model: Literal["haiku", "sonnet", "opus"] = "sonnet"
    working_dir: str | None = None
    timeout: int = 300
    dangerously_skip_permissions: bool = False


class AgentPromptResponse(BaseModel):
    """Response from agent execution."""

    output: str
    success: bool
    session_id: str | None = None
    retry_code: RetryCode = RetryCode.NONE
    error_message: str | None = None
    duration_seconds: float = 0.0


class Task(BaseModel):
    """Task from tasks.md."""

    description: str
    status: TaskStatus = TaskStatus.PENDING
    adw_id: str | None = None
    commit_hash: str | None = None
    error_message: str | None = None
    tags: list[str] = Field(default_factory=list)
    worktree_name: str | None = None
    line_number: int | None = None

    @property
    def is_running(self) -> bool:
        return self.status == TaskStatus.IN_PROGRESS

    @property
    def is_eligible(self) -> bool:
        """Check if task is eligible for pickup.

        A task is eligible if it's in PENDING or BLOCKED status.
        Blocked tasks still need dependency checking to be truly eligible.
        """
        return self.status in (TaskStatus.PENDING, TaskStatus.BLOCKED)

    @property
    def model(self) -> str:
        """Get model from tags, default to sonnet."""
        if "opus" in self.tags:
            return "opus"
        if "haiku" in self.tags:
            return "haiku"
        return "sonnet"

    @property
    def workflow(self) -> str | None:
        """Get workflow from tags if specified.

        Recognized workflow tags:
        - {sdlc} - Full SDLC workflow
        - {simple} - Quick build-only workflow
        - {standard} - Plan-implement-update workflow
        - {bug-fix} or {bugfix} - Focused bug fixing
        - {prototype} - Rapid prototyping

        Returns:
            Workflow name or None if not specified in tags.
        """
        # Known workflow names - check in order of specificity
        workflow_tags = {
            "sdlc": "sdlc",
            "simple": "simple",
            "standard": "standard",
            "bug-fix": "bug-fix",
            "bugfix": "bug-fix",  # Alias
            "prototype": "prototype",
        }

        for tag in self.tags:
            if tag in workflow_tags:
                return workflow_tags[tag]

        return None

    @property
    def priority(self) -> str | None:
        """Get priority from tags if specified.

        Recognized priority tags:
        - {p0} - Critical/immediate
        - {p1} - High priority
        - {p2} - Medium priority
        - {p3} - Low priority

        Returns:
            Priority level (p0-p3) or None if not specified.
        """
        for tag in self.tags:
            if tag in ("p0", "p1", "p2", "p3"):
                return tag

        return None

    @property
    def skip_review(self) -> bool:
        """Check if task should skip review phase.

        Recognized tags:
        - {skip_review} or {skip-review} - Skip review phase
        - {no_review} or {no-review} - Skip review phase

        Returns:
            True if review should be skipped.
        """
        skip_tags = {"skip_review", "skip-review", "no_review", "no-review"}
        return bool(skip_tags & set(self.tags))


class Worktree(BaseModel):
    """Worktree section from tasks.md."""

    name: str
    tasks: list[Task] = Field(default_factory=list)

    def get_eligible_tasks(self) -> list[Task]:
        """Get tasks eligible for execution.

        Rules:
        - [] PENDING tasks are always eligible
        - [⏰] BLOCKED tasks are eligible only if ALL tasks above are [✅] DONE

        This enforces sequential dependencies within a worktree section.
        Tasks are processed in order, with blocked tasks waiting for
        all previous tasks to complete.

        Returns:
            List of tasks eligible for execution.
        """
        eligible = []

        for i, task in enumerate(self.tasks):
            if task.status == TaskStatus.PENDING:
                # Pending tasks are always eligible
                eligible.append(task)
            elif task.status == TaskStatus.BLOCKED:
                # Blocked tasks are eligible only if all tasks above are done
                tasks_above = self.tasks[:i]
                all_done = all(t.status == TaskStatus.DONE for t in tasks_above)
                if all_done:
                    eligible.append(task)

        return eligible
