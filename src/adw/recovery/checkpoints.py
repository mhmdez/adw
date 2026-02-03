"""Checkpoint system for task state persistence.

Saves and restores task state to enable:
- Resuming failed tasks from last successful point
- Rollback to known good states
- Debugging failed attempts
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


@dataclass
class Checkpoint:
    """A saved checkpoint of task state."""

    checkpoint_id: str
    adw_id: str
    phase: str
    step: str
    timestamp: str
    success: bool
    state_snapshot: dict[str, Any]
    files_modified: list[str] = field(default_factory=list)
    git_commit: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert checkpoint to dictionary."""
        return {
            "checkpoint_id": self.checkpoint_id,
            "adw_id": self.adw_id,
            "phase": self.phase,
            "step": self.step,
            "timestamp": self.timestamp,
            "success": self.success,
            "state_snapshot": self.state_snapshot,
            "files_modified": self.files_modified,
            "git_commit": self.git_commit,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Checkpoint:
        """Create checkpoint from dictionary."""
        return cls(
            checkpoint_id=data["checkpoint_id"],
            adw_id=data["adw_id"],
            phase=data["phase"],
            step=data["step"],
            timestamp=data["timestamp"],
            success=data["success"],
            state_snapshot=data.get("state_snapshot", {}),
            files_modified=data.get("files_modified", []),
            git_commit=data.get("git_commit"),
            notes=data.get("notes"),
        )

    def to_json(self, indent: int | None = 2) -> str:
        """Convert checkpoint to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> Checkpoint:
        """Create checkpoint from JSON string."""
        return cls.from_dict(json.loads(json_str))


def _generate_checkpoint_id() -> str:
    """Generate a unique checkpoint ID based on timestamp with microseconds."""
    return datetime.now().strftime("%Y%m%dT%H%M%S%f")


def _get_checkpoints_dir(adw_id: str) -> Path:
    """Get the checkpoints directory for a task."""
    return Path("agents") / adw_id / "checkpoints"


def _get_current_git_commit(worktree_path: Path | None = None) -> str | None:
    """Get the current git commit hash."""
    try:
        cwd = str(worktree_path) if worktree_path else None
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=cwd,
            check=True,
        )
        return result.stdout.strip()[:12]
    except subprocess.CalledProcessError:
        return None


def save_checkpoint(
    adw_id: str,
    phase: str,
    step: str,
    state_snapshot: dict[str, Any],
    success: bool = True,
    files_modified: list[str] | None = None,
    worktree_path: Path | None = None,
    notes: str | None = None,
) -> Checkpoint:
    """Save a checkpoint for a task.

    Args:
        adw_id: The ADW task ID.
        phase: Current workflow phase (e.g., "implement", "test").
        step: Description of the completed step.
        state_snapshot: Dictionary of current state to save.
        success: Whether this step was successful.
        files_modified: List of files modified in this step.
        worktree_path: Optional path to git worktree.
        notes: Optional notes about this checkpoint.

    Returns:
        The created Checkpoint object.
    """
    checkpoint_id = _generate_checkpoint_id()
    git_commit = _get_current_git_commit(worktree_path)

    checkpoint = Checkpoint(
        checkpoint_id=checkpoint_id,
        adw_id=adw_id,
        phase=phase,
        step=step,
        timestamp=datetime.now().isoformat(),
        success=success,
        state_snapshot=state_snapshot,
        files_modified=files_modified or [],
        git_commit=git_commit,
        notes=notes,
    )

    # Save to disk
    checkpoints_dir = _get_checkpoints_dir(adw_id)
    checkpoints_dir.mkdir(parents=True, exist_ok=True)

    checkpoint_path = checkpoints_dir / f"{checkpoint_id}.json"
    checkpoint_path.write_text(checkpoint.to_json())

    return checkpoint


def load_checkpoint(adw_id: str, checkpoint_id: str) -> Checkpoint | None:
    """Load a specific checkpoint.

    Args:
        adw_id: The ADW task ID.
        checkpoint_id: The checkpoint ID to load.

    Returns:
        The Checkpoint object or None if not found.
    """
    checkpoint_path = _get_checkpoints_dir(adw_id) / f"{checkpoint_id}.json"

    if not checkpoint_path.exists():
        return None

    try:
        return Checkpoint.from_json(checkpoint_path.read_text())
    except (json.JSONDecodeError, KeyError):
        return None


def list_checkpoints(adw_id: str) -> list[Checkpoint]:
    """List all checkpoints for a task.

    Args:
        adw_id: The ADW task ID.

    Returns:
        List of Checkpoint objects, sorted by timestamp (newest first).
    """
    checkpoints_dir = _get_checkpoints_dir(adw_id)

    if not checkpoints_dir.exists():
        return []

    checkpoints = []
    for checkpoint_path in checkpoints_dir.glob("*.json"):
        try:
            checkpoint = Checkpoint.from_json(checkpoint_path.read_text())
            checkpoints.append(checkpoint)
        except (json.JSONDecodeError, KeyError):
            continue

    # Sort by timestamp (newest first)
    checkpoints.sort(key=lambda c: c.timestamp, reverse=True)
    return checkpoints


def get_last_checkpoint(adw_id: str, successful_only: bool = False) -> Checkpoint | None:
    """Get the most recent checkpoint for a task.

    Args:
        adw_id: The ADW task ID.
        successful_only: If True, only return successful checkpoints.

    Returns:
        The most recent Checkpoint or None if no checkpoints exist.
    """
    checkpoints = list_checkpoints(adw_id)

    if successful_only:
        checkpoints = [c for c in checkpoints if c.success]

    return checkpoints[0] if checkpoints else None


def get_last_successful_checkpoint(adw_id: str) -> Checkpoint | None:
    """Get the most recent successful checkpoint for a task.

    Args:
        adw_id: The ADW task ID.

    Returns:
        The most recent successful Checkpoint or None.
    """
    return get_last_checkpoint(adw_id, successful_only=True)


def delete_checkpoint(adw_id: str, checkpoint_id: str) -> bool:
    """Delete a specific checkpoint.

    Args:
        adw_id: The ADW task ID.
        checkpoint_id: The checkpoint ID to delete.

    Returns:
        True if deleted, False if not found.
    """
    checkpoint_path = _get_checkpoints_dir(adw_id) / f"{checkpoint_id}.json"

    if not checkpoint_path.exists():
        return False

    checkpoint_path.unlink()
    return True


def clear_checkpoints(adw_id: str) -> int:
    """Delete all checkpoints for a task.

    Args:
        adw_id: The ADW task ID.

    Returns:
        Number of checkpoints deleted.
    """
    checkpoints_dir = _get_checkpoints_dir(adw_id)

    if not checkpoints_dir.exists():
        return 0

    count = 0
    for checkpoint_path in checkpoints_dir.glob("*.json"):
        checkpoint_path.unlink()
        count += 1

    return count


def clear_old_checkpoints(adw_id: str, older_than_days: int = 7) -> int:
    """Delete checkpoints older than specified days.

    Args:
        adw_id: The ADW task ID.
        older_than_days: Delete checkpoints older than this many days.

    Returns:
        Number of checkpoints deleted.
    """
    cutoff = datetime.now() - timedelta(days=older_than_days)
    checkpoints = list_checkpoints(adw_id)

    count = 0
    for checkpoint in checkpoints:
        try:
            checkpoint_time = datetime.fromisoformat(checkpoint.timestamp)
            if checkpoint_time < cutoff:
                if delete_checkpoint(adw_id, checkpoint.checkpoint_id):
                    count += 1
        except ValueError:
            continue

    return count


class CheckpointManager:
    """Manages checkpoints for a task session.

    Provides a higher-level interface for checkpoint operations.
    """

    def __init__(self, adw_id: str, worktree_path: Path | None = None):
        """Initialize checkpoint manager.

        Args:
            adw_id: The ADW task ID.
            worktree_path: Optional path to git worktree.
        """
        self.adw_id = adw_id
        self.worktree_path = worktree_path
        self._current_phase: str | None = None
        self._step_counter: int = 0

    def checkpoint(
        self,
        phase: str,
        step: str,
        state: dict[str, Any],
        success: bool = True,
        files_modified: list[str] | None = None,
        notes: str | None = None,
    ) -> Checkpoint:
        """Save a checkpoint.

        Args:
            phase: Current workflow phase.
            step: Description of the completed step.
            state: Current state to save.
            success: Whether this step was successful.
            files_modified: List of files modified.
            notes: Optional notes.

        Returns:
            The created Checkpoint.
        """
        self._current_phase = phase
        self._step_counter += 1

        return save_checkpoint(
            adw_id=self.adw_id,
            phase=phase,
            step=step,
            state_snapshot=state,
            success=success,
            files_modified=files_modified,
            worktree_path=self.worktree_path,
            notes=notes,
        )

    def get_latest(self, successful_only: bool = False) -> Checkpoint | None:
        """Get the most recent checkpoint.

        Args:
            successful_only: If True, only return successful checkpoints.

        Returns:
            The most recent Checkpoint or None.
        """
        return get_last_checkpoint(self.adw_id, successful_only=successful_only)

    def get_all(self) -> list[Checkpoint]:
        """Get all checkpoints for this task.

        Returns:
            List of Checkpoint objects.
        """
        return list_checkpoints(self.adw_id)

    def restore(self, checkpoint_id: str) -> Checkpoint | None:
        """Load a specific checkpoint.

        Args:
            checkpoint_id: The checkpoint ID to load.

        Returns:
            The Checkpoint or None if not found.
        """
        return load_checkpoint(self.adw_id, checkpoint_id)

    def cleanup(self, older_than_days: int = 7) -> int:
        """Clean up old checkpoints.

        Args:
            older_than_days: Delete checkpoints older than this many days.

        Returns:
            Number of checkpoints deleted.
        """
        return clear_old_checkpoints(self.adw_id, older_than_days)

    def get_resume_context(self) -> dict[str, Any] | None:
        """Get context for resuming from last successful checkpoint.

        Returns:
            Dictionary with resume context or None if no checkpoint.
        """
        checkpoint = get_last_successful_checkpoint(self.adw_id)

        if not checkpoint:
            return None

        return {
            "checkpoint_id": checkpoint.checkpoint_id,
            "phase": checkpoint.phase,
            "step": checkpoint.step,
            "timestamp": checkpoint.timestamp,
            "state": checkpoint.state_snapshot,
            "git_commit": checkpoint.git_commit,
            "files_modified": checkpoint.files_modified,
        }

    def format_resume_prompt(self) -> str | None:
        """Format a prompt for resuming from checkpoint.

        Returns:
            Formatted prompt string or None if no checkpoint.
        """
        context = self.get_resume_context()

        if not context:
            return None

        return (
            f"📍 RESUMING FROM CHECKPOINT\n\n"
            f"Checkpoint ID: {context['checkpoint_id']}\n"
            f"Phase: {context['phase']}\n"
            f"Last Step: {context['step']}\n"
            f"Timestamp: {context['timestamp']}\n"
            f"Git Commit: {context['git_commit'] or 'N/A'}\n\n"
            f"Files Modified:\n" + "\n".join(f"  - {f}" for f in context["files_modified"]) + "\n\n"
            "Please continue from where the task left off.\n"
            "Review the previous work and proceed with the next steps."
        )


def create_wip_commit(
    adw_id: str,
    message: str,
    files: list[str] | None = None,
    worktree_path: Path | None = None,
) -> str | None:
    """Create a WIP (Work In Progress) commit to preserve partial progress.

    Args:
        adw_id: The ADW task ID.
        message: Commit message (will be prefixed with [WIP]).
        files: Specific files to commit (default: all changed files).
        worktree_path: Optional path to git worktree.

    Returns:
        Commit hash if successful, None otherwise.
    """
    cwd = str(worktree_path) if worktree_path else None

    try:
        # Stage files
        if files:
            for file in files:
                subprocess.run(
                    ["git", "add", file],
                    cwd=cwd,
                    check=True,
                    capture_output=True,
                )
        else:
            subprocess.run(
                ["git", "add", "-A"],
                cwd=cwd,
                check=True,
                capture_output=True,
            )

        # Check if there are staged changes
        diff_result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=cwd,
            capture_output=True,
        )

        if diff_result.returncode == 0:
            # No changes to commit
            return None

        # Create WIP commit
        wip_message = f"[WIP] {message}\n\nADW ID: {adw_id}"
        subprocess.run(
            ["git", "commit", "-m", wip_message],
            cwd=cwd,
            check=True,
            capture_output=True,
        )

        # Get commit hash
        hash_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )

        return hash_result.stdout.strip()[:12]

    except subprocess.CalledProcessError:
        return None


def rollback_to_checkpoint(
    adw_id: str,
    checkpoint_id: str | None = None,
    worktree_path: Path | None = None,
) -> bool:
    """Rollback to a specific checkpoint or last successful one.

    This performs a git reset to the checkpoint's commit.

    Args:
        adw_id: The ADW task ID.
        checkpoint_id: Specific checkpoint to rollback to (default: last successful).
        worktree_path: Optional path to git worktree.

    Returns:
        True if rollback successful, False otherwise.
    """
    if checkpoint_id:
        checkpoint = load_checkpoint(adw_id, checkpoint_id)
    else:
        checkpoint = get_last_successful_checkpoint(adw_id)

    if not checkpoint or not checkpoint.git_commit:
        return False

    cwd = str(worktree_path) if worktree_path else None

    try:
        # Reset to checkpoint commit
        subprocess.run(
            ["git", "reset", "--hard", checkpoint.git_commit],
            cwd=cwd,
            check=True,
            capture_output=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def rollback_all_changes(
    adw_id: str,
    worktree_path: Path | None = None,
) -> bool:
    """Rollback all changes made by a task.

    Finds the commit before the task started and resets to it.

    Args:
        adw_id: The ADW task ID.
        worktree_path: Optional path to git worktree.

    Returns:
        True if rollback successful, False otherwise.
    """
    checkpoints = list_checkpoints(adw_id)

    if not checkpoints:
        return False

    # Get the oldest checkpoint (first commit of the task)
    oldest = checkpoints[-1]  # List is sorted newest first

    if not oldest.git_commit:
        return False

    cwd = str(worktree_path) if worktree_path else None

    try:
        # Get the parent of the first checkpoint commit
        result = subprocess.run(
            ["git", "rev-parse", f"{oldest.git_commit}^"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
        parent_commit = result.stdout.strip()

        # Reset to parent
        subprocess.run(
            ["git", "reset", "--hard", parent_commit],
            cwd=cwd,
            check=True,
            capture_output=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False
