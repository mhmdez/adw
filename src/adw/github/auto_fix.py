"""Auto-fix implementation for PR review comments.

Creates mini-tasks from actionable comments and applies fixes.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from .comment_parser import ActionableComment, CommentType
from .review_watcher import reply_to_comment

logger = logging.getLogger(__name__)


class FixStatus(str, Enum):
    """Status of a fix attempt."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class FixResult:
    """Result of attempting to fix a comment."""

    comment_id: int
    status: FixStatus
    commit_hash: str | None = None
    error_message: str | None = None
    changes_made: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "comment_id": self.comment_id,
            "status": self.status.value,
            "commit_hash": self.commit_hash,
            "error_message": self.error_message,
            "changes_made": self.changes_made,
            "duration_seconds": self.duration_seconds,
        }

    @property
    def success(self) -> bool:
        """Check if fix was successful."""
        return self.status == FixStatus.SUCCESS


@dataclass
class AutoFixer:
    """Handles automatic fixing of review comments."""

    pr_number: int
    branch: str
    working_dir: Path
    adw_id: str
    model: str = "sonnet"
    dry_run: bool = False

    def fix_comment(self, comment: ActionableComment) -> FixResult:
        """Attempt to fix a single comment.

        Args:
            comment: The actionable comment to fix.

        Returns:
            FixResult with status and details.
        """
        start_time = datetime.now()

        if comment.comment_type != CommentType.ACTIONABLE:
            return FixResult(
                comment_id=comment.original_comment.id,
                status=FixStatus.SKIPPED,
                error_message="Comment is not actionable",
            )

        desc = comment.action_description[:50]
        logger.info(f"Fixing comment {comment.original_comment.id}: {desc}...")

        if self.dry_run:
            return FixResult(
                comment_id=comment.original_comment.id,
                status=FixStatus.SKIPPED,
                error_message="Dry run mode",
            )

        try:
            # Build the prompt for Claude
            prompt = self._build_fix_prompt(comment)

            # Execute with Claude Code
            result = self._execute_fix(prompt)

            if result["success"]:
                # Commit the changes
                commit_hash = self._commit_changes(comment)

                duration = (datetime.now() - start_time).total_seconds()

                return FixResult(
                    comment_id=comment.original_comment.id,
                    status=FixStatus.SUCCESS,
                    commit_hash=commit_hash,
                    changes_made=result.get("changes", []),
                    duration_seconds=duration,
                )
            else:
                return FixResult(
                    comment_id=comment.original_comment.id,
                    status=FixStatus.FAILED,
                    error_message=result.get("error", "Unknown error"),
                )

        except Exception as e:
            logger.exception(f"Error fixing comment: {e}")
            return FixResult(
                comment_id=comment.original_comment.id,
                status=FixStatus.FAILED,
                error_message=str(e),
            )

    def _build_fix_prompt(self, comment: ActionableComment) -> str:
        """Build a prompt for Claude to fix the comment.

        Args:
            comment: The actionable comment.

        Returns:
            Prompt string for Claude.
        """
        parts = [
            "# PR Review Fix Request",
            "",
            "A reviewer has requested the following change:",
            "",
            f"**Comment:** {comment.action_description}",
        ]

        if comment.file_path:
            parts.append(f"**File:** {comment.file_path}")

        if comment.line_number:
            parts.append(f"**Line:** {comment.line_number}")

        if comment.suggested_change:
            parts.extend(
                [
                    "",
                    "**Suggested code:**",
                    "```",
                    comment.suggested_change,
                    "```",
                ]
            )

        parts.extend(
            [
                "",
                "## Instructions",
                "",
                "1. Read the relevant file(s) to understand context",
                "2. Implement the requested change",
                "3. Ensure the change is minimal and focused",
                "4. Do not change unrelated code",
                "5. Verify your change works (no syntax errors)",
                "",
                f"Priority: {comment.priority.value}",
            ]
        )

        return "\n".join(parts)

    def _execute_fix(self, prompt: str) -> dict[str, Any]:
        """Execute the fix using Claude Code.

        Args:
            prompt: The prompt for Claude.

        Returns:
            Dict with success status and details.
        """
        try:
            # Run claude command
            result = subprocess.run(
                [
                    "claude",
                    "--dangerously-skip-permissions",
                    "-p",
                    prompt,
                ],
                cwd=self.working_dir,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            if result.returncode == 0:
                # Check if there are actual changes
                diff_result = subprocess.run(
                    ["git", "diff", "--stat"],
                    cwd=self.working_dir,
                    capture_output=True,
                    text=True,
                )

                changes = []
                if diff_result.stdout.strip():
                    # Parse changed files from diff stat
                    for line in diff_result.stdout.strip().split("\n"):
                        if "|" in line:
                            file_name = line.split("|")[0].strip()
                            changes.append(file_name)

                return {
                    "success": True,
                    "output": result.stdout,
                    "changes": changes,
                }
            else:
                return {
                    "success": False,
                    "error": result.stderr or "Claude command failed",
                }

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Fix timed out after 5 minutes"}
        except subprocess.SubprocessError as e:
            return {"success": False, "error": str(e)}

    def _commit_changes(self, comment: ActionableComment) -> str | None:
        """Commit the changes for a fix.

        Args:
            comment: The comment being fixed.

        Returns:
            Commit hash or None if failed.
        """
        try:
            # Stage all changes
            subprocess.run(
                ["git", "add", "-A"],
                cwd=self.working_dir,
                check=True,
            )

            # Build commit message
            short_desc = comment.action_description[:50]
            if len(comment.action_description) > 50:
                short_desc += "..."

            commit_msg = f"fix: address review comment\n\n{short_desc}\n\n"

            if comment.file_path:
                commit_msg += f"File: {comment.file_path}\n"

            commit_msg += f"\nComment ID: {comment.original_comment.id}"
            commit_msg += f"\nADW ID: {self.adw_id}"

            # Commit
            result = subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=self.working_dir,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                logger.warning(f"Commit failed: {result.stderr}")
                return None

            # Get commit hash
            hash_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.working_dir,
                capture_output=True,
                text=True,
            )

            if hash_result.returncode == 0:
                return hash_result.stdout.strip()[:8]

            return None

        except subprocess.SubprocessError as e:
            logger.error(f"Failed to commit: {e}")
            return None

    def fix_comments_batch(
        self,
        comments: list[ActionableComment],
        batch_commit: bool = True,
    ) -> list[FixResult]:
        """Fix multiple comments, optionally batching into one commit.

        Args:
            comments: List of actionable comments to fix.
            batch_commit: If True, create one commit for all fixes.

        Returns:
            List of FixResult objects.
        """
        results = []

        if batch_commit:
            # Apply all fixes then commit once
            changes_made = []
            failed = []

            for comment in comments:
                if comment.comment_type != CommentType.ACTIONABLE:
                    results.append(
                        FixResult(
                            comment_id=comment.original_comment.id,
                            status=FixStatus.SKIPPED,
                        )
                    )
                    continue

                prompt = self._build_fix_prompt(comment)
                fix_result = self._execute_fix(prompt)

                if fix_result["success"]:
                    changes_made.extend(fix_result.get("changes", []))
                    results.append(
                        FixResult(
                            comment_id=comment.original_comment.id,
                            status=FixStatus.PENDING,  # Will be updated after commit
                            changes_made=fix_result.get("changes", []),
                        )
                    )
                else:
                    failed.append(comment.original_comment.id)
                    results.append(
                        FixResult(
                            comment_id=comment.original_comment.id,
                            status=FixStatus.FAILED,
                            error_message=fix_result.get("error"),
                        )
                    )

            # Commit all successful changes
            if changes_made:
                commit_hash = self._commit_batch(comments, changes_made)

                # Update results with commit hash
                for result in results:
                    if result.status == FixStatus.PENDING:
                        result.status = FixStatus.SUCCESS
                        result.commit_hash = commit_hash

        else:
            # Individual commits for each fix
            for comment in comments:
                result = self.fix_comment(comment)
                results.append(result)

        return results

    def _commit_batch(
        self,
        comments: list[ActionableComment],
        changes: list[str],
    ) -> str | None:
        """Create a batch commit for multiple fixes.

        Args:
            comments: List of comments being fixed.
            changes: List of changed files.

        Returns:
            Commit hash or None if failed.
        """
        try:
            subprocess.run(
                ["git", "add", "-A"],
                cwd=self.working_dir,
                check=True,
            )

            # Build commit message
            commit_msg = "fix: address multiple review comments\n\n"
            commit_msg += "Addressed the following review comments:\n\n"

            for comment in comments:
                if comment.comment_type == CommentType.ACTIONABLE:
                    short_desc = comment.action_description[:60]
                    if len(comment.action_description) > 60:
                        short_desc += "..."
                    commit_msg += f"- {short_desc}\n"

            commit_msg += f"\nADW ID: {self.adw_id}"

            result = subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=self.working_dir,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                logger.warning(f"Batch commit failed: {result.stderr}")
                return None

            hash_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.working_dir,
                capture_output=True,
                text=True,
            )

            if hash_result.returncode == 0:
                return hash_result.stdout.strip()[:8]

            return None

        except subprocess.SubprocessError as e:
            logger.error(f"Failed to batch commit: {e}")
            return None

    def push_changes(self) -> bool:
        """Push committed changes to remote.

        Returns:
            True if successful.
        """
        try:
            result = subprocess.run(
                ["git", "push"],
                cwd=self.working_dir,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                logger.error(f"Push failed: {result.stderr}")
                return False

            return True

        except subprocess.SubprocessError as e:
            logger.error(f"Failed to push: {e}")
            return False

    def notify_reviewer(self, result: FixResult, comment: ActionableComment) -> bool:
        """Notify reviewer that comment was addressed.

        Args:
            result: The fix result.
            comment: The original comment.

        Returns:
            True if notification sent.
        """
        if not result.success:
            return False

        changes_str = ""
        if result.changes_made:
            changes_str = "\n".join(f"- {c}" for c in result.changes_made)
            changes_str = f"\n\n**Changed files:**\n{changes_str}"

        body = f"Fixed in commit `{result.commit_hash}`.{changes_str}"

        return reply_to_comment(
            self.pr_number,
            comment.original_comment.id,
            body,
        )


def apply_review_fixes(
    pr_number: int,
    comments: list[ActionableComment],
    working_dir: Path,
    adw_id: str,
    branch: str = "",
    notify: bool = True,
    dry_run: bool = False,
) -> list[FixResult]:
    """Apply fixes for review comments.

    Convenience function that creates an AutoFixer and processes comments.

    Args:
        pr_number: The PR number.
        comments: List of actionable comments.
        working_dir: Working directory for the repo.
        adw_id: ADW ID for tracking.
        branch: Branch name (optional).
        notify: Whether to notify reviewers.
        dry_run: If True, don't actually make changes.

    Returns:
        List of FixResult objects.
    """
    fixer = AutoFixer(
        pr_number=pr_number,
        branch=branch,
        working_dir=working_dir,
        adw_id=adw_id,
        dry_run=dry_run,
    )

    # Filter to actionable only
    actionable = [c for c in comments if c.is_actionable]

    if not actionable:
        logger.info("No actionable comments to fix")
        return []

    # Fix comments
    results = fixer.fix_comments_batch(actionable)

    # Push if we have successful fixes
    successful = [r for r in results if r.success]
    if successful and not dry_run:
        fixer.push_changes()

        # Notify reviewers
        if notify:
            for result, comment in zip(results, actionable):
                if result.success:
                    fixer.notify_reviewer(result, comment)

    return results
