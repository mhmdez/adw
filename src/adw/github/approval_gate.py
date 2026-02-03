"""Human-in-the-loop approval gates for ADW.

Provides plan approval gates, task approval, and iterative feedback.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ApprovalStatus(str, Enum):
    """Status of an approval request."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class TaskApprovalStatus(str, Enum):
    """Extended task status for approval flow."""

    PENDING = "pending"
    BLOCKED = "blocked"
    AWAITING_REVIEW = "awaiting_review"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"


@dataclass
class ContinuePrompt:
    """A continue prompt with iterative feedback."""

    prompt: str
    timestamp: datetime
    phase: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "prompt": self.prompt,
            "timestamp": self.timestamp.isoformat(),
            "phase": self.phase,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContinuePrompt:
        """Create from dictionary."""
        return cls(
            prompt=data["prompt"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            phase=data.get("phase"),
        )


@dataclass
class ApprovalRequest:
    """An approval request for a task or plan."""

    task_id: str
    title: str
    description: str
    proposed_plan: str
    files_to_modify: list[str] = field(default_factory=list)
    effort_estimate: str | None = None
    risk_assessment: str | None = None
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime | None = None
    rejection_reason: str | None = None
    continue_prompts: list[ContinuePrompt] = field(default_factory=list)
    reviewer: str | None = None
    approved_at: datetime | None = None
    rejected_at: datetime | None = None

    def __post_init__(self) -> None:
        """Set expiration if not provided."""
        if self.expires_at is None:
            self.expires_at = self.created_at + timedelta(hours=24)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "task_id": self.task_id,
            "title": self.title,
            "description": self.description,
            "proposed_plan": self.proposed_plan,
            "files_to_modify": self.files_to_modify,
            "effort_estimate": self.effort_estimate,
            "risk_assessment": self.risk_assessment,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "rejection_reason": self.rejection_reason,
            "continue_prompts": [p.to_dict() for p in self.continue_prompts],
            "reviewer": self.reviewer,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "rejected_at": self.rejected_at.isoformat() if self.rejected_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ApprovalRequest:
        """Create from dictionary."""
        return cls(
            task_id=data["task_id"],
            title=data["title"],
            description=data["description"],
            proposed_plan=data["proposed_plan"],
            files_to_modify=data.get("files_to_modify", []),
            effort_estimate=data.get("effort_estimate"),
            risk_assessment=data.get("risk_assessment"),
            status=ApprovalStatus(data.get("status", "pending")),
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=(datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None),
            rejection_reason=data.get("rejection_reason"),
            continue_prompts=[ContinuePrompt.from_dict(p) for p in data.get("continue_prompts", [])],
            reviewer=data.get("reviewer"),
            approved_at=(datetime.fromisoformat(data["approved_at"]) if data.get("approved_at") else None),
            rejected_at=(datetime.fromisoformat(data["rejected_at"]) if data.get("rejected_at") else None),
        )

    @property
    def is_pending(self) -> bool:
        """Check if request is still pending."""
        return self.status == ApprovalStatus.PENDING

    @property
    def is_expired(self) -> bool:
        """Check if request has expired."""
        if self.status != ApprovalStatus.PENDING:
            return False
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at

    def to_markdown(self) -> str:
        """Generate markdown representation for approval request.

        Returns:
            Markdown string for the approval request.
        """
        lines = [
            f"# Approval Request: {self.title}",
            "",
            f"**Task ID:** `{self.task_id}`",
            f"**Status:** {self.status.value}",
            f"**Created:** {self.created_at.strftime('%Y-%m-%d %H:%M')}",
        ]

        if self.expires_at:
            lines.append(f"**Expires:** {self.expires_at.strftime('%Y-%m-%d %H:%M')}")

        lines.extend(
            [
                "",
                "## Description",
                "",
                self.description,
                "",
                "## Proposed Plan",
                "",
                self.proposed_plan,
            ]
        )

        if self.files_to_modify:
            lines.extend(
                [
                    "",
                    "## Files to Modify",
                    "",
                ]
            )
            for f in self.files_to_modify:
                lines.append(f"- `{f}`")

        if self.effort_estimate:
            lines.extend(
                [
                    "",
                    "## Effort Estimate",
                    "",
                    self.effort_estimate,
                ]
            )

        if self.risk_assessment:
            lines.extend(
                [
                    "",
                    "## Risk Assessment",
                    "",
                    self.risk_assessment,
                ]
            )

        if self.continue_prompts:
            lines.extend(
                [
                    "",
                    "## Feedback History",
                    "",
                ]
            )
            for prompt in self.continue_prompts:
                lines.append(f"- [{prompt.timestamp.strftime('%Y-%m-%d %H:%M')}] {prompt.prompt}")

        if self.rejection_reason:
            lines.extend(
                [
                    "",
                    "## Rejection Reason",
                    "",
                    self.rejection_reason,
                ]
            )

        lines.extend(
            [
                "",
                "---",
                "",
                "To approve: `adw approve " + self.task_id + "`",
                "",
                "To reject: `adw reject " + self.task_id + ' --reason "your reason"`',
                "",
                "To provide feedback: `adw continue " + self.task_id + ' "your feedback"`',
            ]
        )

        return "\n".join(lines)


def _get_approvals_dir(base_path: Path | None = None) -> Path:
    """Get the approvals directory, creating if needed."""
    path = base_path or Path.cwd()
    approvals_dir = path / ".adw" / "approvals"
    approvals_dir.mkdir(parents=True, exist_ok=True)
    return approvals_dir


def _get_approval_path(task_id: str, base_path: Path | None = None) -> Path:
    """Get the path for an approval request file."""
    approvals_dir = _get_approvals_dir(base_path)
    return approvals_dir / f"{task_id}.json"


def _get_agents_dir(task_id: str, base_path: Path | None = None) -> Path:
    """Get the agents directory for a task."""
    path = base_path or Path.cwd()
    agents_dir = path / "agents" / task_id
    agents_dir.mkdir(parents=True, exist_ok=True)
    return agents_dir


def create_approval_request(
    task_id: str,
    title: str,
    description: str,
    proposed_plan: str,
    files_to_modify: list[str] | None = None,
    effort_estimate: str | None = None,
    risk_assessment: str | None = None,
    base_path: Path | None = None,
) -> ApprovalRequest:
    """Create a new approval request.

    Args:
        task_id: The task ID.
        title: Title of the task.
        description: Task description.
        proposed_plan: The proposed implementation plan.
        files_to_modify: List of files that will be modified.
        effort_estimate: Estimated effort.
        risk_assessment: Risk assessment.
        base_path: Base path for storage.

    Returns:
        The created ApprovalRequest.
    """
    request = ApprovalRequest(
        task_id=task_id,
        title=title,
        description=description,
        proposed_plan=proposed_plan,
        files_to_modify=files_to_modify or [],
        effort_estimate=effort_estimate,
        risk_assessment=risk_assessment,
    )

    # Save to approval directory
    approval_path = _get_approval_path(task_id, base_path)
    approval_path.write_text(json.dumps(request.to_dict(), indent=2))

    # Also save markdown version in agents directory
    agents_dir = _get_agents_dir(task_id, base_path)
    md_path = agents_dir / "APPROVAL_REQUEST.md"
    md_path.write_text(request.to_markdown())

    logger.info(f"Created approval request for task {task_id}")

    return request


def load_approval_request(
    task_id: str,
    base_path: Path | None = None,
) -> ApprovalRequest | None:
    """Load an existing approval request.

    Args:
        task_id: The task ID.
        base_path: Base path for storage.

    Returns:
        ApprovalRequest or None if not found.
    """
    approval_path = _get_approval_path(task_id, base_path)

    if not approval_path.exists():
        return None

    try:
        data = json.loads(approval_path.read_text())
        request = ApprovalRequest.from_dict(data)

        # Check if expired
        if request.is_expired:
            request.status = ApprovalStatus.EXPIRED
            _save_approval_request(request, base_path)

        return request

    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Failed to load approval request: {e}")
        return None


def _save_approval_request(
    request: ApprovalRequest,
    base_path: Path | None = None,
) -> None:
    """Save an approval request.

    Args:
        request: The request to save.
        base_path: Base path for storage.
    """
    approval_path = _get_approval_path(request.task_id, base_path)
    approval_path.write_text(json.dumps(request.to_dict(), indent=2))

    # Update markdown version
    agents_dir = _get_agents_dir(request.task_id, base_path)
    md_path = agents_dir / "APPROVAL_REQUEST.md"
    md_path.write_text(request.to_markdown())


def approve_task(
    task_id: str,
    reviewer: str | None = None,
    base_path: Path | None = None,
) -> ApprovalRequest | None:
    """Approve a task.

    Args:
        task_id: The task ID to approve.
        reviewer: Optional reviewer name.
        base_path: Base path for storage.

    Returns:
        Updated ApprovalRequest or None if not found.
    """
    request = load_approval_request(task_id, base_path)

    if not request:
        logger.error(f"No approval request found for task {task_id}")
        return None

    if not request.is_pending:
        logger.warning(f"Task {task_id} is not pending approval (status: {request.status})")
        return request

    request.status = ApprovalStatus.APPROVED
    request.approved_at = datetime.now()
    request.reviewer = reviewer

    _save_approval_request(request, base_path)

    logger.info(f"Approved task {task_id}")

    return request


def reject_task(
    task_id: str,
    reason: str,
    reviewer: str | None = None,
    base_path: Path | None = None,
) -> ApprovalRequest | None:
    """Reject a task with a reason.

    Args:
        task_id: The task ID to reject.
        reason: Rejection reason.
        reviewer: Optional reviewer name.
        base_path: Base path for storage.

    Returns:
        Updated ApprovalRequest or None if not found.
    """
    request = load_approval_request(task_id, base_path)

    if not request:
        logger.error(f"No approval request found for task {task_id}")
        return None

    if not request.is_pending:
        logger.warning(f"Task {task_id} is not pending approval (status: {request.status})")
        return request

    request.status = ApprovalStatus.REJECTED
    request.rejected_at = datetime.now()
    request.rejection_reason = reason
    request.reviewer = reviewer

    _save_approval_request(request, base_path)

    logger.info(f"Rejected task {task_id}: {reason}")

    return request


def add_continue_prompt(
    task_id: str,
    prompt: str,
    phase: str | None = None,
    base_path: Path | None = None,
) -> ApprovalRequest | None:
    """Add a continue prompt to a task.

    Args:
        task_id: The task ID.
        prompt: The feedback/instruction to add.
        phase: Optional phase context.
        base_path: Base path for storage.

    Returns:
        Updated ApprovalRequest or None if not found.
    """
    request = load_approval_request(task_id, base_path)

    if not request:
        logger.error(f"No approval request found for task {task_id}")
        return None

    continue_prompt = ContinuePrompt(
        prompt=prompt,
        timestamp=datetime.now(),
        phase=phase,
    )

    request.continue_prompts.append(continue_prompt)

    _save_approval_request(request, base_path)

    logger.info(f"Added continue prompt to task {task_id}")

    return request


def list_pending_approvals(base_path: Path | None = None) -> list[ApprovalRequest]:
    """List all pending approval requests.

    Args:
        base_path: Base path for storage.

    Returns:
        List of pending ApprovalRequest objects.
    """
    approvals_dir = _get_approvals_dir(base_path)
    pending = []

    for path in approvals_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text())
            request = ApprovalRequest.from_dict(data)

            # Update expired status
            if request.is_expired:
                request.status = ApprovalStatus.EXPIRED
                _save_approval_request(request, base_path)

            if request.is_pending:
                pending.append(request)

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to load approval {path.name}: {e}")

    # Sort by creation date
    pending.sort(key=lambda r: r.created_at)

    return pending


def get_approval_context(
    task_id: str,
    base_path: Path | None = None,
) -> str:
    """Get context string for injection into agent prompts.

    Includes rejection reason and continue prompts.

    Args:
        task_id: The task ID.
        base_path: Base path for storage.

    Returns:
        Context string for agent prompt.
    """
    request = load_approval_request(task_id, base_path)

    if not request:
        return ""

    parts = []

    if request.rejection_reason:
        parts.extend(
            [
                "## Previous Rejection",
                "",
                "This task was previously rejected with the following reason:",
                "",
                f"> {request.rejection_reason}",
                "",
                "Please address this feedback in your revised plan.",
                "",
            ]
        )

    if request.continue_prompts:
        parts.extend(
            [
                "## Additional Feedback",
                "",
            ]
        )
        for prompt in request.continue_prompts:
            parts.append(f"- {prompt.prompt}")
        parts.append("")

    return "\n".join(parts)


@dataclass
class ApprovalGate:
    """Gate that pauses task execution for human approval.

    Use this to enforce human-in-the-loop review before implementation.
    """

    enabled: bool = True
    auto_approve_low_risk: bool = False
    require_approval_for: list[str] = field(default_factory=lambda: ["plan", "implement"])

    def __post_init__(self) -> None:
        """Initialize from environment if enabled not set."""
        # Check environment variable
        env_auto = os.environ.get("ADW_AUTO_APPROVE", "").lower()
        if env_auto in ("1", "true", "yes"):
            self.enabled = False

    def requires_approval(self, phase: str) -> bool:
        """Check if a phase requires approval.

        Args:
            phase: The phase name.

        Returns:
            True if approval is required.
        """
        if not self.enabled:
            return False

        return phase.lower() in self.require_approval_for

    def create_gate(
        self,
        task_id: str,
        title: str,
        description: str,
        proposed_plan: str,
        files_to_modify: list[str] | None = None,
        risk_level: str | None = None,
        base_path: Path | None = None,
    ) -> ApprovalRequest:
        """Create an approval gate for a task.

        Args:
            task_id: The task ID.
            title: Task title.
            description: Task description.
            proposed_plan: The proposed plan.
            files_to_modify: Files to be modified.
            risk_level: Risk level (low, medium, high).
            base_path: Base path for storage.

        Returns:
            ApprovalRequest for the gate.
        """
        # Auto-approve low risk if enabled
        if self.auto_approve_low_risk and risk_level == "low":
            request = create_approval_request(
                task_id=task_id,
                title=title,
                description=description,
                proposed_plan=proposed_plan,
                files_to_modify=files_to_modify,
                risk_assessment=f"Risk Level: {risk_level}",
                base_path=base_path,
            )
            approve_task(task_id, reviewer="auto", base_path=base_path)
            return request

        return create_approval_request(
            task_id=task_id,
            title=title,
            description=description,
            proposed_plan=proposed_plan,
            files_to_modify=files_to_modify,
            risk_assessment=f"Risk Level: {risk_level}" if risk_level else None,
            base_path=base_path,
        )

    def wait_for_approval(
        self,
        task_id: str,
        base_path: Path | None = None,
        timeout_seconds: int | None = None,
    ) -> ApprovalStatus:
        """Wait for approval (blocking).

        In practice, this would be used in polling mode.
        For CLI usage, prefer checking status manually.

        Args:
            task_id: The task ID.
            base_path: Base path for storage.
            timeout_seconds: Maximum wait time.

        Returns:
            Final ApprovalStatus.
        """
        import time

        start = datetime.now()
        check_interval = 5  # seconds

        while True:
            request = load_approval_request(task_id, base_path)

            if not request:
                return ApprovalStatus.EXPIRED

            if not request.is_pending:
                return request.status

            if timeout_seconds:
                elapsed = (datetime.now() - start).total_seconds()
                if elapsed > timeout_seconds:
                    return ApprovalStatus.EXPIRED

            time.sleep(check_interval)
