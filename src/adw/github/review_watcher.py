"""PR review watcher for ADW.

Polls for review comments on ADW-created PRs and tracks state.
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class PRStatus(str, Enum):
    """Pull request status."""

    OPEN = "open"
    CLOSED = "closed"
    MERGED = "merged"
    DRAFT = "draft"


@dataclass
class ReviewComment:
    """A review comment from a PR."""

    id: int
    body: str
    author: str
    path: str | None = None  # File path for inline comments
    line: int | None = None  # Line number for inline comments
    created_at: datetime | None = None
    updated_at: datetime | None = None
    in_reply_to_id: int | None = None
    commit_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "body": self.body,
            "author": self.author,
            "path": self.path,
            "line": self.line,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "in_reply_to_id": self.in_reply_to_id,
            "commit_id": self.commit_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReviewComment:
        """Create from dictionary."""
        return cls(
            id=data["id"],
            body=data["body"],
            author=data["author"],
            path=data.get("path"),
            line=data.get("line"),
            created_at=(datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None),
            updated_at=(datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None),
            in_reply_to_id=data.get("in_reply_to_id"),
            commit_id=data.get("commit_id"),
        )


@dataclass
class PRInfo:
    """Pull request information."""

    number: int
    title: str
    state: PRStatus
    is_draft: bool = False
    head_branch: str = ""
    base_branch: str = "main"
    author: str = ""
    url: str = ""
    mergeable: bool | None = None
    review_decision: str | None = None  # APPROVED, CHANGES_REQUESTED, REVIEW_REQUIRED

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "number": self.number,
            "title": self.title,
            "state": self.state.value,
            "is_draft": self.is_draft,
            "head_branch": self.head_branch,
            "base_branch": self.base_branch,
            "author": self.author,
            "url": self.url,
            "mergeable": self.mergeable,
            "review_decision": self.review_decision,
        }


def get_pr_status(pr_number: int) -> PRInfo | None:
    """Get pull request status and information.

    Args:
        pr_number: The PR number to check.

    Returns:
        PRInfo or None if not found.
    """
    try:
        json_fields = "number,title,state,isDraft,headRefName,baseRefName,author,url,mergeable,reviewDecision"
        result = subprocess.run(
            ["gh", "pr", "view", str(pr_number), "--json", json_fields],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            logger.error(f"Failed to get PR status: {result.stderr}")
            return None

        data = json.loads(result.stdout)

        # Map state to enum
        state_str = data.get("state", "OPEN").upper()
        if state_str == "MERGED":
            state = PRStatus.MERGED
        elif state_str == "CLOSED":
            state = PRStatus.CLOSED
        elif data.get("isDraft"):
            state = PRStatus.DRAFT
        else:
            state = PRStatus.OPEN

        return PRInfo(
            number=data["number"],
            title=data["title"],
            state=state,
            is_draft=data.get("isDraft", False),
            head_branch=data.get("headRefName", ""),
            base_branch=data.get("baseRefName", "main"),
            author=data.get("author", {}).get("login", ""),
            url=data.get("url", ""),
            mergeable=data.get("mergeable"),
            review_decision=data.get("reviewDecision"),
        )

    except (json.JSONDecodeError, KeyError, subprocess.SubprocessError) as e:
        logger.error(f"Error getting PR status: {e}")
        return None


def get_pr_review_comments(pr_number: int) -> list[ReviewComment]:
    """Get all review comments for a PR.

    Uses GitHub CLI to fetch review comments.

    Args:
        pr_number: The PR number.

    Returns:
        List of ReviewComment objects.
    """
    comments = []

    try:
        # Get review comments (inline comments on files)
        result = subprocess.run(
            [
                "gh",
                "api",
                f"repos/{{owner}}/{{repo}}/pulls/{pr_number}/comments",
                "--jq",
                ".",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0 and result.stdout.strip():
            try:
                data = json.loads(result.stdout)
                for item in data:
                    comment = ReviewComment(
                        id=item["id"],
                        body=item.get("body", ""),
                        author=item.get("user", {}).get("login", "unknown"),
                        path=item.get("path"),
                        line=item.get("line") or item.get("original_line"),
                        created_at=_parse_datetime(item.get("created_at")),
                        updated_at=_parse_datetime(item.get("updated_at")),
                        in_reply_to_id=item.get("in_reply_to_id"),
                        commit_id=item.get("commit_id"),
                    )
                    comments.append(comment)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse review comments: {e}")

        # Also get issue comments (general PR comments)
        result = subprocess.run(
            [
                "gh",
                "api",
                f"repos/{{owner}}/{{repo}}/issues/{pr_number}/comments",
                "--jq",
                ".",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0 and result.stdout.strip():
            try:
                data = json.loads(result.stdout)
                for item in data:
                    comment = ReviewComment(
                        id=item["id"],
                        body=item.get("body", ""),
                        author=item.get("user", {}).get("login", "unknown"),
                        path=None,  # Issue comments don't have file paths
                        line=None,
                        created_at=_parse_datetime(item.get("created_at")),
                        updated_at=_parse_datetime(item.get("updated_at")),
                    )
                    comments.append(comment)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse issue comments: {e}")

    except subprocess.SubprocessError as e:
        logger.error(f"Error fetching PR comments: {e}")

    return comments


def _parse_datetime(dt_str: str | None) -> datetime | None:
    """Parse ISO datetime string."""
    if not dt_str:
        return None
    try:
        # Handle GitHub's datetime format
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except ValueError:
        return None


def reply_to_comment(pr_number: int, comment_id: int, body: str) -> bool:
    """Reply to a review comment.

    Args:
        pr_number: The PR number.
        comment_id: The comment ID to reply to.
        body: Reply body text.

    Returns:
        True if successful.
    """
    try:
        result = subprocess.run(
            [
                "gh",
                "api",
                f"repos/{{owner}}/{{repo}}/pulls/{pr_number}/comments",
                "-X",
                "POST",
                "-f",
                f"body={body}",
                "-F",
                f"in_reply_to={comment_id}",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            logger.error(f"Failed to reply to comment: {result.stderr}")
            return False

        return True

    except subprocess.SubprocessError as e:
        logger.error(f"Error replying to comment: {e}")
        return False


def add_pr_comment(pr_number: int, body: str, adw_id: str | None = None) -> bool:
    """Add a general comment to a PR.

    Args:
        pr_number: The PR number.
        body: Comment body text.
        adw_id: Optional ADW ID to include as marker.

    Returns:
        True if successful.
    """
    # Add ADW marker if provided
    if adw_id:
        body = f"<!-- ADW:{adw_id} -->\n{body}"

    try:
        result = subprocess.run(
            ["gh", "pr", "comment", str(pr_number), "--body", body],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            logger.error(f"Failed to add PR comment: {result.stderr}")
            return False

        return True

    except subprocess.SubprocessError as e:
        logger.error(f"Error adding PR comment: {e}")
        return False


@dataclass
class PRReviewWatcher:
    """Watches a PR for new review comments.

    Tracks which comments have been seen to avoid duplicates.
    """

    pr_number: int
    state_file: Path | None = None
    seen_comment_ids: set[int] = field(default_factory=set)
    last_check: datetime | None = None

    def __post_init__(self) -> None:
        """Load state from file if it exists."""
        if self.state_file and self.state_file.exists():
            self._load_state()

    def _load_state(self) -> None:
        """Load seen comments from state file."""
        if not self.state_file:
            return

        try:
            data = json.loads(self.state_file.read_text())
            self.seen_comment_ids = set(data.get("seen_comment_ids", []))
            if data.get("last_check"):
                self.last_check = datetime.fromisoformat(data["last_check"])
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load watcher state: {e}")

    def _save_state(self) -> None:
        """Save seen comments to state file."""
        if not self.state_file:
            return

        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "seen_comment_ids": list(self.seen_comment_ids),
                "last_check": self.last_check.isoformat() if self.last_check else None,
            }
            self.state_file.write_text(json.dumps(data, indent=2))
        except OSError as e:
            logger.warning(f"Failed to save watcher state: {e}")

    def get_new_comments(self) -> list[ReviewComment]:
        """Fetch and return only new comments since last check.

        Returns:
            List of new ReviewComment objects.
        """
        all_comments = get_pr_review_comments(self.pr_number)

        new_comments = [c for c in all_comments if c.id not in self.seen_comment_ids]

        # Update seen IDs
        for comment in new_comments:
            self.seen_comment_ids.add(comment.id)

        self.last_check = datetime.now()
        self._save_state()

        return new_comments

    def mark_comment_seen(self, comment_id: int) -> None:
        """Mark a comment as seen.

        Args:
            comment_id: The comment ID to mark.
        """
        self.seen_comment_ids.add(comment_id)
        self._save_state()

    def get_pr_info(self) -> PRInfo | None:
        """Get current PR status.

        Returns:
            PRInfo or None if not found.
        """
        return get_pr_status(self.pr_number)

    def is_approved(self) -> bool:
        """Check if PR is approved.

        Returns:
            True if PR has been approved.
        """
        info = self.get_pr_info()
        return info is not None and info.review_decision == "APPROVED"

    def is_changes_requested(self) -> bool:
        """Check if changes are requested.

        Returns:
            True if changes have been requested.
        """
        info = self.get_pr_info()
        return info is not None and info.review_decision == "CHANGES_REQUESTED"


def watch_pr_comments(
    pr_number: int,
    callback: Any,  # Callable[[list[ReviewComment]], None]
    interval: int = 60,
    state_file: Path | None = None,
) -> None:
    """Continuously watch for new PR comments.

    Args:
        pr_number: The PR number to watch.
        callback: Function to call with new comments.
        interval: Seconds between checks.
        state_file: Optional file to persist state.
    """
    watcher = PRReviewWatcher(
        pr_number=pr_number,
        state_file=state_file,
    )

    logger.info(f"Starting PR watcher for #{pr_number}")

    try:
        while True:
            # Check PR status
            info = watcher.get_pr_info()
            if not info:
                logger.error(f"Could not get PR info for #{pr_number}")
                time.sleep(interval)
                continue

            # Stop watching if PR is closed/merged
            if info.state in (PRStatus.CLOSED, PRStatus.MERGED):
                logger.info(f"PR #{pr_number} is {info.state.value}, stopping watcher")
                break

            # Get new comments
            new_comments = watcher.get_new_comments()

            if new_comments:
                logger.info(f"Found {len(new_comments)} new comments on PR #{pr_number}")
                callback(new_comments)

            time.sleep(interval)

    except KeyboardInterrupt:
        logger.info("Stopping PR watcher")
